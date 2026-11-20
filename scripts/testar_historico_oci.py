"""Validação manual do serviço com OCI real e dados fictícios."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv


RAIZ = Path(__file__).resolve().parents[1]


def conferir(condicao, mensagem):
    if not condicao:
        raise RuntimeError(mensagem)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Grava três documentos fictícios, seus resultados "
            "e históricos no OCI real."
        )
    )
    parser.add_argument(
        "--executar-real",
        action="store_true",
        help="Habilita explicitamente a gravação no bucket real.",
    )
    argumentos = parser.parse_args()

    if not argumentos.executar_real:
        parser.error(
            "Use --executar-real para habilitar a gravação no bucket."
        )

    load_dotenv(RAIZ / ".env")

    # Configuração limitada a este processo.
    os.environ["OCI_OBRIGATORIO"] = "true"
    os.environ["OCI_SIMULACAO_HABILITADA"] = "false"
    os.environ["LIMIAR_CONFIANCA"] = "0.85"

    from src.api.service import TriagemService
    from src.schemas import TriagemMediFlow
    from src.storage.oci_storage import OCIStorage

    storage = OCIStorage.das_configuracoes()

    conferir(
        storage.bucket == "mediflow-documentos",
        "Bucket diferente do esperado. Confira OCI_BUCKET_NAME.",
    )

    execucao = uuid4().hex
    pasta = RAIZ / "temp" / "validacao_historico_oci" / execucao
    pasta.mkdir(parents=True, exist_ok=False)

    relatorio = {
        "execucao": execucao,
        "iniciado_em": datetime.now(timezone.utc).isoformat(),
        "bucket": storage.bucket,
        "ambiente": "maquina local",
        "armazenamento_real": True,
        "gemini_utilizado": False,
        "casos": [],
        "concluido": False,
    }

    arquivo_relatorio = pasta / "relatorio.json"

    def salvar_relatorio():
        arquivo_relatorio.write_text(
            json.dumps(
                relatorio,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    casos = [
        (
            "rotina",
            (
                "DOCUMENTO FICTICIO - USO EXCLUSIVO EM TESTES\n"
                "LAUDO DE RADIOGRAFIA\n"
                "Paciente: Pessoa Ficticia Alfa\n"
                "Idade: 42\n"
                "Médico: Profissional Ficticio Alfa\n"
                "CRM/SP: 123456\n"
                "Diagnóstico: Exame sem alterações.\n"
            ),
            "PROCESSADO",
            "PRONTUARIO_ELETRONICO",
            False,
        ),
        (
            "urgencia",
            (
                "DOCUMENTO FICTICIO - USO EXCLUSIVO EM TESTES\n"
                "LAUDO DE TOMOGRAFIA\n"
                "Paciente: Pessoa Ficticia Beta\n"
                "Idade: 61\n"
                "Médico: Profissional Ficticio Beta\n"
                "CRM/SP: 234567\n"
                "Diagnóstico: TEP agudo. URGENTE.\n"
            ),
            "PROCESSADO",
            "FILA_URGENCIA_MEDICA",
            False,
        ),
        (
            "revisao",
            (
                "DOCUMENTO FICTICIO - USO EXCLUSIVO EM TESTES\n"
                "RECEITA MEDICA\n"
                "Paciente: Pessoa Ficticia Gama\n"
                "Idade: 55\n"
            ),
            "EM_REVISAO",
            "FILA_REVISAO_HUMANA",
            True,
        ),
    ]

    salvar_relatorio()

    for nome, texto, status, destino, revisao in casos:
        documento_id = f"DOC-OCI-{nome.upper()}-{uuid4().hex}"
        caso = {
            "cenario": nome,
            "documento_id": documento_id,
            "validado": False,
        }
        relatorio["casos"].append(caso)
        salvar_relatorio()

        service = TriagemService(storage=storage)
        service.submeter_texto(
            texto=texto,
            documento_id=documento_id,
            canal_origem="VALIDACAO_OCI_FICTICIA",
        )

        triagem = service.executar_triagem(documento_id)

        conferir(
            triagem.status.value == status,
            f"{nome}: status diferente do esperado.",
        )
        conferir(
            triagem.armazenamento_oci.status_backup == "sucesso",
            f"{nome}: persistência não confirmada.",
        )
        conferir(
            triagem.armazenamento_oci.modo_simulacao is False,
            f"{nome}: resposta identificada como simulação.",
        )

        doc = service._documentos_originais[documento_id]
        original = (
            f"recebidos/{documento_id}/original."
            f"{doc.formato.lower()}"
        )
        resultado = triagem.armazenamento_oci.caminho_objeto
        historico = service.obter_referencia_historico_oci(
            documento_id
        )

        conferir(resultado, f"{nome}: caminho do resultado ausente.")
        conferir(historico, f"{nome}: histórico não confirmado.")

        caso.update({
            "original": original,
            "resultado": resultado,
            "historico": historico,
        })
        salvar_relatorio()

        bytes_original = storage.ler_bytes(original)
        bytes_resultado = storage.ler_bytes(resultado)
        bytes_historico = storage.ler_bytes(historico)

        conferir(
            bytes_original == texto.encode("utf-8"),
            f"{nome}: original baixado diferente do enviado.",
        )

        resultado_json = json.loads(
            bytes_resultado.decode("utf-8")
        )
        historico_json = json.loads(
            bytes_historico.decode("utf-8")
        )

        # Reutiliza o contrato oficial para validar o JSON baixado.
        TriagemMediFlow.model_validate(resultado_json)

        conferir(
            resultado_json == triagem.model_dump(mode="json"),
            f"{nome}: resultado gravado diferente do serviço.",
        )
        conferir(
            resultado_json["documento_id"] == documento_id,
            f"{nome}: ID incorreto no resultado.",
        )

        decisao = resultado_json["decisao_roteamento"]
        conferir(
            destino in decisao["destinos"],
            f"{nome}: destino esperado não encontrado.",
        )
        conferir(
            decisao["requer_auditoria_humana"] is revisao,
            f"{nome}: indicador de revisão diferente do esperado.",
        )

        eventos = [
            evento.model_dump(mode="json")
            for evento in service.obter_historico(documento_id)
        ]

        conferir(
            historico_json["documento_id"] == documento_id,
            f"{nome}: ID incorreto no histórico.",
        )
        conferir(
            historico_json["eventos"] == eventos,
            f"{nome}: eventos gravados diferentes do serviço.",
        )

        tipos = [evento["tipo_evento"] for evento in eventos]
        conferir(
            tipos[:2] == ["RECEBIDO", "PROCESSANDO"]
            and tipos[-1] == "ROTEADO",
            f"{nome}: sequência de eventos inesperada.",
        )

        for evento in eventos:
            conferir(
                evento["documento_id"] == documento_id,
                f"{nome}: evento associado a outro documento.",
            )

        for caminho in (original, resultado, historico):
            conferir(
                caminho in storage.listar(caminho),
                f"{nome}: objeto não encontrado na listagem.",
            )

        destino_local = pasta / nome
        destino_local.mkdir()

        (destino_local / "original.txt").write_bytes(bytes_original)
        (destino_local / "resultado.json").write_bytes(bytes_resultado)
        (destino_local / "historico.json").write_bytes(bytes_historico)

        caso.update({
            "validado": True,
            "status": resultado_json["status"],
            "destinos": decisao["destinos"],
            "eventos": tipos,
            "original_identico": True,
            "resultado_identico": True,
            "historico_identico": True,
        })
        salvar_relatorio()

        print(f"\nCENARIO OK: {nome}", flush=True)
        print(f"DOCUMENTO: {documento_id}", flush=True)
        print(f"ORIGINAL: {original}", flush=True)
        print(f"RESULTADO: {resultado}", flush=True)
        print(f"HISTORICO: {historico}", flush=True)
        print("LEITURA E COMPARACAO: OK", flush=True)

    relatorio["concluido"] = True
    salvar_relatorio()

    print("\nTRES CENARIOS VALIDADOS NO OCI REAL.")
    print(f"EVIDENCIAS LOCAIS: {pasta}")


if __name__ == "__main__":
    try:
        main()
    except Exception as erro:
        # Evita imprimir credenciais ou detalhes completos do SDK.
        status_http = getattr(erro, "status", None)
        print(
            "\nVALIDACAO INTERROMPIDA. "
            f"Tipo: {type(erro).__name__}; "
            f"HTTP: {status_http if status_http is not None else 'n/a'}."
        )
        print(
            "Nao considere a validacao concluida. "
            "Confira o relatorio parcial na pasta temp."
        )
        raise SystemExit(1)