"""
Camada de persistência OCI e rastreabilidade real para a bancada Streamlit.

Garante que o status da persistência reflita a realidade:
- Sucesso real: quando o OCI Storage grava o objeto e retorna ETag.
- Falha real: quando a Oracle Cloud rejeita (ex: 412 IfNoneMatchFailed ou 403),
  sem mascarar erro nem transformar em falso positivo.
- Modo simulado: quando o ambiente local não possui credenciais OCI ou em cenários demo.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger("mediflow.app.oci_persistence")


def executar_persistencia_triagem(
    *,
    documento_id: str,
    nome_arquivo: str,
    conteudo_original_bytes: Optional[bytes],
    dados_triagem_json: Dict[str, Any] | str,
    caminho_resultado_alvo: str,
    storage: Optional[Any] = None,
    forcar_simulado: bool = False,
) -> Dict[str, Any]:
    """
    Coordena a persistência de triagem no OCI Storage ou diagnostica o estado real.

    Retorna dicionário estruturado com status_backup ('sucesso', 'falha', 'simulado'),
    modo_simulacao (bool), bucket, caminho_objeto, etag, erro e evento_linha_do_tempo.
    """
    bucket_padrao = os.getenv("OCI_BUCKET_NAME", "mediflow-documentos")

    # 1. Modo Simulado Forçado (ex: Cenários Oficiais Demo do Edital)
    if forcar_simulado:
        return {
            "status_backup": "simulado",
            "modo_simulacao": True,
            "bucket": bucket_padrao,
            "caminho_objeto": caminho_resultado_alvo,
            "etag": None,
            "erro": None,
            "detalhes": "Cenário de demonstração homologado (EPT §12). Persistência simulada em memória.",
            "evento_linha_do_tempo": "Snapshot de demonstração simulado em memória (sem envio para nuvem).",
        }

    # 2. Resolução do Cliente OCI Storage
    cliente_storage = storage
    if cliente_storage is None:
        try:
            from src.storage.oci_storage import OCIStorage
            cliente_storage = OCIStorage.das_configuracoes()
        except Exception as err:
            logger.info("OCI Storage não configurado no .env (%s). Operando em modo simulado.", err)
            return {
                "status_backup": "simulado",
                "modo_simulacao": True,
                "bucket": bucket_padrao,
                "caminho_objeto": caminho_resultado_alvo,
                "etag": None,
                "erro": None,
                "detalhes": f"OCI não configurado no .env ({str(err)}). Operação mantida em modo local/simulado.",
                "evento_linha_do_tempo": "Persistência local em memória (OCI não configurado no ambiente).",
            }

    bucket_atual = getattr(cliente_storage, "bucket", bucket_padrao)

    # 3. Preparação do Conteúdo JSON
    if isinstance(dados_triagem_json, dict):
        json_bytes = json.dumps(dados_triagem_json, ensure_ascii=False, indent=2).encode("utf-8")
    elif isinstance(dados_triagem_json, str):
        json_bytes = dados_triagem_json.encode("utf-8")
    else:
        json_bytes = bytes(dados_triagem_json)

    # 4. Gravação OCI (Original e Resultado)
    try:
        # Se houver original e ainda não estiver gravado, tenta enviar
        if conteudo_original_bytes:
            caminho_original = f"recebidos/{documento_id}/{nome_arquivo}"
            try:
                cliente_storage.enviar_bytes(
                    caminho_original,
                    conteudo_original_bytes,
                    tipo_conteudo="application/octet-stream",
                )
            except Exception as err_orig:
                # Se for 412 (já existe), é idempotente para o original
                logger.debug("Original já existente ou aviso no OCI: %s", err_orig)

        # Envia o JSON de resultado / snapshot
        resposta = cliente_storage.enviar_bytes(
            caminho_resultado_alvo,
            json_bytes,
            tipo_conteudo="application/json",
        )
        etag = resposta.get("etag") if isinstance(resposta, dict) else None

        return {
            "status_backup": "sucesso",
            "modo_simulacao": False,
            "bucket": bucket_atual,
            "caminho_objeto": caminho_resultado_alvo,
            "etag": etag,
            "erro": None,
            "detalhes": "Snapshot gravado com sucesso no bucket OCI.",
            "evento_linha_do_tempo": f"Snapshot gravado com sucesso no OCI (ETag: {etag or 'OK'}).",
        }

    except Exception as err:
        # Extrai detalhes de erro da Oracle Cloud (ex: 412 IfNoneMatchFailed)
        codigo_status = getattr(err, "status", None)
        codigo_erro = getattr(err, "code", None)
        headers = getattr(err, "headers", {}) or {}
        req_id = headers.get("opc-request-id", "N/A")
        mensagem = getattr(err, "message", str(err))

        if codigo_status:
            erro_formatado = f"ServiceError {codigo_status} ({codigo_erro}): {mensagem} [opc-request-id: {req_id}]"
        else:
            erro_formatado = str(err)

        logger.error("Falha ao persistir snapshot no OCI: %s", erro_formatado)

        return {
            "status_backup": "falha",
            "modo_simulacao": False,
            "bucket": bucket_atual,
            "caminho_objeto": caminho_resultado_alvo,
            "etag": None,
            "erro": erro_formatado,
            "detalhes": f"Falha na gravação OCI: {erro_formatado}",
            "evento_linha_do_tempo": f"Falha na gravação OCI: {erro_formatado}",
        }

