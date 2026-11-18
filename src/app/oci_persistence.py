"""
Camada de persistência OCI e rastreabilidade real para a bancada Streamlit.

Garante que o status da persistência reflita a realidade sem falso sucesso:
- Sucesso real: quando o OCI Object Storage confirma a gravação do documento original
  e do resultado JSON (com conferência byte a byte em caso de HTTP 412).
- Falha real: quando o envio do original ou do resultado falha ou diverge, expondo
  apenas mensagem pública segura na interface/JSON e registrando detalhes técnicos
  (incluindo opc-request-id) exclusivamente nos logs internos.
- Modo simulado: quando o ambiente local não possui credenciais OCI ou em cenários demo.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("mediflow.app.oci_persistence")

MENSAGEM_PUBLICA_FALHA_OCI = (
    "Não foi possível confirmar a gravação dos objetos no OCI Object Storage."
)
MENSAGEM_PUBLICA_SIMULADO_CONFIG = (
    "Armazenamento OCI não configurado neste ambiente. Operando em modo local simulado."
)
MENSAGEM_PUBLICA_SIMULADO_DEMO = (
    "Cenário de demonstração homologado (EPT §12). Persistência simulada em memória."
)


def resolver_caminho_original_oci(documento_id: str, nome_arquivo: str) -> str:
    """Padroniza o caminho do documento bruto em recebidos/{id}/original.{ext}."""
    sufixo = Path(nome_arquivo or "").suffix.lstrip(".").lower()
    ext = sufixo if (sufixo and sufixo.isalnum()) else "bin"
    return f"recebidos/{documento_id}/original.{ext}"


def resolver_caminho_resultado_oci(documento_id: str, status: Any, urgente: bool) -> str:
    """Segrega o caminho do resultado no OCI por status funcional e urgência (RF-29 / RN-08)."""
    status_val = getattr(status, "value", str(status)).upper()
    if status_val == "EM_REVISAO":
        return f"auditoria_humana/{documento_id}/resultado.json"
    prefixo = "processados/urgentes" if urgente else "processados"
    return f"{prefixo}/{documento_id}/resultado.json"


def _eh_erro_412(err: Exception) -> bool:
    status_cod = getattr(err, "status", None)
    code_cod = getattr(err, "code", None)
    return (
        status_cod == 412
        or str(status_cod) == "412"
        or code_cod in ("PreconditionFailed", "IfNoneMatchFailed")
    )


def _enviar_com_conferencia_412(
    *,
    cliente_storage: Any,
    caminho: str,
    conteudo: bytes,
    tipo_conteudo: str,
) -> Dict[str, Any]:
    """
    Envia bytes ao OCI. Em caso de HTTP 412 (objeto já existente), só confirma
    idempotência após verificar que os bytes armazenados são idênticos aos enviados.
    """
    try:
        resposta = cliente_storage.enviar_bytes(
            caminho,
            conteudo,
            tipo_conteudo=tipo_conteudo,
        )
    except Exception as err_envio:
        if not _eh_erro_412(err_envio):
            raise

        ler_bytes = getattr(cliente_storage, "ler_bytes", None)
        if not callable(ler_bytes):
            raise RuntimeError(
                f"Conflito 412 em '{caminho}' sem suporte de leitura para conferência."
            ) from err_envio

        conteudo_existente = ler_bytes(caminho)
        if not isinstance(conteudo_existente, bytes) or conteudo_existente != conteudo:
            raise RuntimeError(
                f"Conflito de integridade OCI em '{caminho}': conteúdo armazenado diverge do enviado."
            ) from err_envio

        logger.info("Objeto já existente no OCI com integridade confirmada (%s).", caminho)
        return {
            "caminho_objeto": caminho,
            "etag": "confirmado-por-integridade",
            "status_backup": "sucesso",
        }

    if isinstance(resposta, dict) and resposta.get("status_backup") not in (None, "sucesso"):
        raise RuntimeError(f"OCI não confirmou o status de gravação para '{caminho}'.")

    return resposta if isinstance(resposta, dict) else {"caminho_objeto": caminho, "etag": None}


def _registrar_erro_interno_oci(etapa: str, err: Exception) -> None:
    codigo_status = getattr(err, "status", None)
    codigo_erro = getattr(err, "code", None)
    headers = getattr(err, "headers", None) or {}
    req_id = headers.get("opc-request-id", "N/A") if isinstance(headers, dict) else "N/A"
    mensagem = getattr(err, "message", str(err))

    if codigo_status:
        detalhe_log = (
            f"ServiceError {codigo_status} ({codigo_erro}): {mensagem} "
            f"[opc-request-id: {req_id}]"
        )
    else:
        detalhe_log = str(err)

    logger.error("Falha ao persistir %s no OCI: %s", etapa, detalhe_log)


def _eh_ausencia_credenciais_oci(err: Exception) -> bool:
    """
    Distingue ambiente local sem OCI configurado de falhas reais de credencial/chave
    ou de modo estrito OCI_OBRIGATORIO=true (EF v1.2 RF-28, RF-30, §12 e §16.10).
    """
    if os.getenv("OCI_OBRIGATORIO", "false").strip().lower() in ("true", "1"):
        return False
    if not isinstance(err, ValueError):
        return False
    msg = str(err)
    if not msg.startswith("Preencha no .env:"):
        return False
    faltantes = {
        item.strip()
        for item in msg.partition(":")[2].split(",")
        if item.strip()
    }
    return {"OCI_USER_OCID", "OCI_KEY_FILE"}.issubset(faltantes)


def executar_persistencia_triagem(
    *,
    documento_id: str,
    nome_arquivo: str,
    conteudo_original_bytes: Optional[bytes],
    dados_triagem_json: Dict[str, Any] | str,
    caminho_resultado_alvo: str,
    storage: Optional[Any] = None,
    forcar_simulado: bool = False,
    mime_original: str = "application/octet-stream",
) -> Dict[str, Any]:
    """
    Coordena a persistência durável (original + resultado) no OCI Storage.

    Retorna dicionário estruturado com mensagens públicas seguras e sem falso sucesso.
    """
    bucket_padrao = os.getenv("OCI_BUCKET_NAME", "mediflow-documentos")
    caminho_original = resolver_caminho_original_oci(documento_id, nome_arquivo)

    # 1. Modo Simulado Forçado (Cenários Oficiais Demo / modo simulado explícito)
    if forcar_simulado:
        return {
            "status_backup": "simulado",
            "modo_simulacao": True,
            "bucket": bucket_padrao,
            "caminho_objeto": caminho_resultado_alvo,
            "caminho_alvo": caminho_resultado_alvo,
            "caminho_original": caminho_original,
            "etag": None,
            "erro": None,
            "detalhes": MENSAGEM_PUBLICA_SIMULADO_DEMO,
            "evento_linha_do_tempo": "Snapshot de demonstração simulado em memória (sem envio externo ao OCI).",
        }

    # 2. Resolução do Cliente OCI Storage
    cliente_storage = storage
    if cliente_storage is None:
        try:
            from src.storage.oci_storage import OCIStorage

            cliente_storage = OCIStorage.das_configuracoes()
        except Exception as err:
            if _eh_ausencia_credenciais_oci(err):
                logger.info("OCI Storage não configurado. Operando em modo simulado.")
                return {
                    "status_backup": "simulado",
                    "modo_simulacao": True,
                    "bucket": bucket_padrao,
                    "caminho_objeto": caminho_resultado_alvo,
                    "caminho_alvo": caminho_resultado_alvo,
                    "caminho_original": caminho_original,
                    "etag": None,
                    "erro": None,
                    "detalhes": MENSAGEM_PUBLICA_SIMULADO_CONFIG,
                    "evento_linha_do_tempo": "Persistência local em memória (OCI não configurado no ambiente).",
                }

            _registrar_erro_interno_oci("inicialização do conector OCI", err)
            return {
                "status_backup": "falha",
                "modo_simulacao": False,
                "bucket": bucket_padrao,
                "caminho_objeto": None,
                "caminho_alvo": caminho_resultado_alvo,
                "caminho_original": caminho_original,
                "etag": None,
                "erro": MENSAGEM_PUBLICA_FALHA_OCI,
                "detalhes": MENSAGEM_PUBLICA_FALHA_OCI,
                "evento_linha_do_tempo": "Falha ao inicializar ou validar credenciais do OCI Object Storage.",
            }

    bucket_atual = getattr(cliente_storage, "bucket", bucket_padrao)

    # 3. Preparação do Conteúdo JSON
    if isinstance(dados_triagem_json, dict):
        json_bytes = json.dumps(dados_triagem_json, ensure_ascii=False, indent=2).encode("utf-8")
    elif isinstance(dados_triagem_json, str):
        json_bytes = dados_triagem_json.encode("utf-8")
    else:
        json_bytes = bytes(dados_triagem_json)

    # 4. Gravação OCI Independente (Original + Resultado) — falha em qualquer um invalida confirmação
    falha_original = False
    if not conteudo_original_bytes:
        logger.error(
            "Falha ao persistir original no OCI: conteúdo binário ausente para documento %s.",
            documento_id,
        )
        falha_original = True
    else:
        try:
            _enviar_com_conferencia_412(
                cliente_storage=cliente_storage,
                caminho=caminho_original,
                conteudo=conteudo_original_bytes,
                tipo_conteudo=mime_original,
            )
        except Exception as err_orig:
            _registrar_erro_interno_oci(f"documento original ({caminho_original})", err_orig)
            falha_original = True

    falha_resultado = False
    etag: Optional[str] = None
    try:
        resposta = _enviar_com_conferencia_412(
            cliente_storage=cliente_storage,
            caminho=caminho_resultado_alvo,
            conteudo=json_bytes,
            tipo_conteudo="application/json",
        )
        etag = resposta.get("etag") if isinstance(resposta, dict) else None
    except Exception as err_res:
        _registrar_erro_interno_oci(f"resultado ({caminho_resultado_alvo})", err_res)
        falha_resultado = True

    if falha_original or falha_resultado:
        return {
            "status_backup": "falha",
            "modo_simulacao": False,
            "bucket": bucket_atual,
            "caminho_objeto": None,
            "caminho_alvo": caminho_resultado_alvo,
            "caminho_original": caminho_original,
            "etag": None,
            "erro": MENSAGEM_PUBLICA_FALHA_OCI,
            "detalhes": MENSAGEM_PUBLICA_FALHA_OCI,
            "evento_linha_do_tempo": "Falha ao confirmar a gravação durável no OCI Object Storage.",
        }

    return {
        "status_backup": "sucesso",
        "modo_simulacao": False,
        "bucket": bucket_atual,
        "caminho_objeto": caminho_resultado_alvo,
        "caminho_alvo": caminho_resultado_alvo,
        "caminho_original": caminho_original,
        "etag": etag,
        "erro": None,
        "detalhes": "Documento original e resultado JSON confirmados no bucket OCI.",
        "evento_linha_do_tempo": f"Objetos confirmados no OCI (ETag: {etag or 'OK'}).",
    }
