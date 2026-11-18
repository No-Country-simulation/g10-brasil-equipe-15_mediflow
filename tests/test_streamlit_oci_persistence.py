"""
Testes TDD para a camada de persistência OCI do Streamlit.

Verifica que 'executar_persistencia_triagem' e os resolvedores de caminho atendem:
1. Gravação confirmada do documento original e do JSON de resultado com ETag.
2. Falha no documento original NUNCA vira falso sucesso, mesmo quando o JSON é salvo.
3. HTTP 412 (objeto existente) só é aceito após conferir que os bytes armazenados são idênticos.
4. Mensagens públicas fixas e seguras na UI/JSON, restringindo ServiceError e opc-request-id aos logs internos.
5. Segregação por status funcional (processados/, processados/urgentes/, auditoria_humana/).
"""
import logging
from unittest.mock import Mock, patch

import oci
import pytest

from src.app.oci_persistence import (
    MENSAGEM_PUBLICA_FALHA_OCI,
    executar_persistencia_triagem,
    resolver_caminho_original_oci,
    resolver_caminho_resultado_oci,
)
from src.schemas import StatusTriagem


def test_resolver_caminhos_oci_segregacao_por_status():
    """Garante segregação estrita em recebidos/, processados/, processados/urgentes/ e auditoria_humana/."""
    assert (
        resolver_caminho_original_oci("DOC-001", "Exame Sangue.PDF")
        == "recebidos/DOC-001/original.pdf"
    )
    assert (
        resolver_caminho_resultado_oci("DOC-001", StatusTriagem.PROCESSADO, urgente=False)
        == "processados/DOC-001/resultado.json"
    )
    assert (
        resolver_caminho_resultado_oci("DOC-002", StatusTriagem.PROCESSADO, urgente=True)
        == "processados/urgentes/DOC-002/resultado.json"
    )
    assert (
        resolver_caminho_resultado_oci("DOC-003", StatusTriagem.EM_REVISAO, urgente=False)
        == "auditoria_humana/DOC-003/resultado.json"
    )
    # Urgência com ambiguidade (EM_REVISAO) segrega sob auditoria_humana/
    assert (
        resolver_caminho_resultado_oci("DOC-004", StatusTriagem.EM_REVISAO, urgente=True)
        == "auditoria_humana/DOC-004/resultado.json"
    )


def test_persistencia_oci_sucesso_envia_original_e_resultado_com_etag():
    """Quando original e JSON são confirmados no OCI, retorna status_backup='sucesso' e ETag."""
    storage_mock = Mock()
    storage_mock.bucket = "mediflow-documentos"
    storage_mock.enviar_bytes.side_effect = [
        {
            "bucket": "mediflow-documentos",
            "caminho_objeto": "recebidos/DOC-001/original.txt",
            "etag": "etag-orig-001",
            "status_backup": "sucesso",
        },
        {
            "bucket": "mediflow-documentos",
            "caminho_objeto": "processados/DOC-001/resultado.json",
            "etag": "etag-res-12345",
            "status_backup": "sucesso",
        },
    ]

    resultado = executar_persistencia_triagem(
        documento_id="DOC-001",
        nome_arquivo="receita.txt",
        conteudo_original_bytes=b"Conteudo da receita",
        dados_triagem_json={"status": "PROCESSADO", "documento_id": "DOC-001"},
        caminho_resultado_alvo="processados/DOC-001/resultado.json",
        storage=storage_mock,
        forcar_simulado=False,
        mime_original="text/plain",
    )

    assert resultado["status_backup"] == "sucesso"
    assert resultado["modo_simulacao"] is False
    assert resultado["etag"] == "etag-res-12345"
    assert resultado["bucket"] == "mediflow-documentos"
    assert resultado["caminho_original"] == "recebidos/DOC-001/original.txt"
    assert resultado["caminho_objeto"] == "processados/DOC-001/resultado.json"
    assert resultado["erro"] is None
    assert storage_mock.enviar_bytes.call_count == 2


def test_persistencia_oci_falha_no_original_mesmo_com_json_salvo_retorna_falha(caplog):
    """Se o envio do documento original falhar, o resultado NUNCA pode ser sucesso, e a gravação do JSON é abortada."""
    storage_mock = Mock()
    storage_mock.bucket = "mediflow-documentos"
    storage_mock.enviar_bytes.side_effect = oci.exceptions.ServiceError(
        status=503,
        code="ServiceUnavailable",
        headers={"opc-request-id": "req-orig-503"},
        message="OCI bucket temporarily unavailable.",
    )

    with caplog.at_level(logging.ERROR, logger="mediflow.app.oci_persistence"):
        resultado = executar_persistencia_triagem(
            documento_id="DOC-001",
            nome_arquivo="receita.txt",
            conteudo_original_bytes=b"Conteudo da receita",
            dados_triagem_json={"status": "PROCESSADO", "documento_id": "DOC-001"},
            caminho_resultado_alvo="processados/DOC-001/resultado.json",
            storage=storage_mock,
            forcar_simulado=False,
        )

    assert resultado["status_backup"] == "falha"
    assert resultado["modo_simulacao"] is False
    assert resultado["caminho_objeto"] is None
    assert resultado["erro"] == MENSAGEM_PUBLICA_FALHA_OCI
    assert "req-orig-503" not in resultado["erro"]
    assert "ServiceUnavailable" not in resultado["detalhes"]
    assert "req-orig-503" in caplog.text
    # Garante atomicidade: falha no original impede chamada para gravar resultado.json
    assert storage_mock.enviar_bytes.call_count == 1
    assert storage_mock.enviar_bytes.call_args[0][0] == "recebidos/DOC-001/original.txt"


def test_persistencia_oci_falha_original_impede_gravacao_de_resultado_com_falso_sucesso_no_bucket():
    """Garante que se o original falhar, nenhum resultado.json é gravado no bucket com falso sucesso."""
    storage_mock = Mock()
    storage_mock.bucket = "mediflow-documentos"
    storage_mock.enviar_bytes.side_effect = RuntimeError("Falha de rede ao gravar original")

    payload_candidato = {
        "status": "PROCESSADO",
        "documento_id": "DOC-FAIL-ORIG",
        "armazenamento_oci": {
            "bucket": "mediflow-documentos",
            "caminho_objeto": "processados/DOC-FAIL-ORIG/resultado.json",
            "status_backup": "sucesso",
            "modo_simulacao": False,
        },
    }

    resultado = executar_persistencia_triagem(
        documento_id="DOC-FAIL-ORIG",
        nome_arquivo="receita.txt",
        conteudo_original_bytes=b"Conteudo original",
        dados_triagem_json=payload_candidato,
        caminho_resultado_alvo="processados/DOC-FAIL-ORIG/resultado.json",
        storage=storage_mock,
        forcar_simulado=False,
    )

    assert resultado["status_backup"] == "falha"
    assert storage_mock.enviar_bytes.call_count == 1
    assert storage_mock.enviar_bytes.call_args[0][0] == "recebidos/DOC-FAIL-ORIG/original.txt"
    caminhos_totais = [call[0][0] for call in storage_mock.enviar_bytes.call_args_list]
    assert "processados/DOC-FAIL-ORIG/resultado.json" not in caminhos_totais


def test_persistencia_oci_original_412_conteudo_identico_confirma_idempotencia():
    """Em HTTP 412 no original, confirma gravação somente após verificar que ler_bytes retorna bytes idênticos."""
    conteudo_orig = b"Conteudo identico da receita"
    storage_mock = Mock()
    storage_mock.bucket = "mediflow-documentos"
    storage_mock.enviar_bytes.side_effect = [
        oci.exceptions.ServiceError(
            status=412,
            code="IfNoneMatchFailed",
            headers={"opc-request-id": "req-412-ok"},
            message="Entity tag did not match.",
        ),
        {
            "bucket": "mediflow-documentos",
            "caminho_objeto": "processados/DOC-001/resultado.json",
            "etag": "etag-res-ok",
            "status_backup": "sucesso",
        },
    ]
    storage_mock.ler_bytes.return_value = conteudo_orig

    resultado = executar_persistencia_triagem(
        documento_id="DOC-001",
        nome_arquivo="receita.txt",
        conteudo_original_bytes=conteudo_orig,
        dados_triagem_json={"status": "PROCESSADO", "documento_id": "DOC-001"},
        caminho_resultado_alvo="processados/DOC-001/resultado.json",
        storage=storage_mock,
        forcar_simulado=False,
    )

    assert resultado["status_backup"] == "sucesso"
    assert resultado["etag"] == "etag-res-ok"
    storage_mock.ler_bytes.assert_called_once_with("recebidos/DOC-001/original.txt")


def test_persistencia_oci_original_412_conteudo_divergente_retorna_falha(caplog):
    """Em HTTP 412 no original, se o conteúdo no bucket divergir do enviado, deve sinalizar falha e abortar."""
    storage_mock = Mock()
    storage_mock.bucket = "mediflow-documentos"
    storage_mock.enviar_bytes.side_effect = oci.exceptions.ServiceError(
        status=412,
        code="IfNoneMatchFailed",
        headers={"opc-request-id": "req-412-div"},
        message="Entity tag did not match.",
    )
    storage_mock.ler_bytes.return_value = b"OUTRO CONTEUDO DIVERGENTE"

    with caplog.at_level(logging.ERROR, logger="mediflow.app.oci_persistence"):
        resultado = executar_persistencia_triagem(
            documento_id="DOC-001",
            nome_arquivo="receita.txt",
            conteudo_original_bytes=b"Conteudo esperado",
            dados_triagem_json={"status": "PROCESSADO", "documento_id": "DOC-001"},
            caminho_resultado_alvo="processados/DOC-001/resultado.json",
            storage=storage_mock,
            forcar_simulado=False,
        )

    assert resultado["status_backup"] == "falha"
    assert resultado["caminho_objeto"] is None
    assert resultado["erro"] == MENSAGEM_PUBLICA_FALHA_OCI
    assert "diverge" in caplog.text
    assert storage_mock.enviar_bytes.call_count == 1


def test_persistencia_oci_falha_412_sanitiza_mensagem_publica_e_mantem_detalhe_no_log(caplog):
    """Detalhes do OCI (ServiceError, código e opc-request-id) ficam nos logs internos, nunca na UI/JSON."""
    storage_mock = Mock()
    storage_mock.bucket = "mediflow-documentos"
    storage_mock.enviar_bytes.side_effect = oci.exceptions.ServiceError(
        status=412,
        code="IfNoneMatchFailed",
        headers={"opc-request-id": "req-gru-412"},
        message="The current entity tag did not match the if-none-match condition.",
    )
    storage_mock.ler_bytes.side_effect = RuntimeError("Objeto inacessível")

    with caplog.at_level(logging.ERROR, logger="mediflow.app.oci_persistence"):
        resultado = executar_persistencia_triagem(
            documento_id="DOC-001",
            nome_arquivo="receita.txt",
            conteudo_original_bytes=b"Conteudo da receita",
            dados_triagem_json={"status": "PROCESSADO", "documento_id": "DOC-001"},
            caminho_resultado_alvo="processados/DOC-001/resultado.json",
            storage=storage_mock,
            forcar_simulado=False,
        )

    assert resultado["status_backup"] == "falha"
    assert resultado["modo_simulacao"] is False
    assert resultado["etag"] is None
    assert resultado["erro"] == MENSAGEM_PUBLICA_FALHA_OCI
    assert resultado["detalhes"] == MENSAGEM_PUBLICA_FALHA_OCI
    for termo_interno in ("412", "IfNoneMatchFailed", "req-gru-412", "ServiceError"):
        assert termo_interno not in resultado["erro"]
        assert termo_interno not in resultado["detalhes"]
        assert termo_interno not in resultado["evento_linha_do_tempo"]


def test_persistencia_oci_sem_credenciais_retorna_modo_simulado_sem_vazar_env():
    """Quando o OCI não está configurado no .env (ausência total), opera em modo simulado sem expor variáveis internas."""
    with patch(
        "src.storage.oci_storage.OCIStorage.das_configuracoes",
        side_effect=ValueError(
            "Preencha no .env: OCI_USER_OCID, OCI_TENANCY_OCID, OCI_FINGERPRINT, OCI_KEY_FILE, OCI_NAMESPACE"
        ),
    ):
        resultado = executar_persistencia_triagem(
            documento_id="DOC-002",
            nome_arquivo="laudo.pdf",
            conteudo_original_bytes=b"%PDF-1.4",
            dados_triagem_json={"status": "EM_REVISAO", "documento_id": "DOC-002"},
            caminho_resultado_alvo="auditoria_humana/DOC-002/resultado.json",
            storage=None,
            forcar_simulado=False,
        )

        assert resultado["status_backup"] == "simulado"
        assert resultado["modo_simulacao"] is True
        assert resultado["etag"] is None
        assert "OCI_USER_OCID" not in resultado["detalhes"]
        assert "OCI_KEY_FILE" not in resultado["detalhes"]
        assert "simulad" in resultado["detalhes"].lower()


def test_persistencia_oci_forcar_simulado_cenario_demo():
    """Para cenários oficiais demo do edital, permanece em modo simulado sem acessar nuvem."""
    storage_mock = Mock()

    resultado = executar_persistencia_triagem(
        documento_id="DOC-DEMO-01",
        nome_arquivo="01_rotina.pdf",
        conteudo_original_bytes=b"%PDF-1.4",
        dados_triagem_json={"status": "PROCESSADO", "documento_id": "DOC-DEMO-01"},
        caminho_resultado_alvo="processados/DOC-DEMO-01/resultado.json",
        storage=storage_mock,
        forcar_simulado=True,
    )

    assert resultado["status_backup"] == "simulado"
    assert resultado["modo_simulacao"] is True
    assert storage_mock.enviar_bytes.call_count == 0


def test_persistencia_oci_obrigatorio_ativo_sem_credenciais_retorna_falha(monkeypatch):
    """EF v1.2 RF-30 / §16.10: com OCI_OBRIGATORIO=true, ausência de credenciais retorna falha (nunca simulado)."""
    monkeypatch.setenv("OCI_OBRIGATORIO", "true")
    with patch(
        "src.storage.oci_storage.OCIStorage.das_configuracoes",
        side_effect=ValueError(
            "Preencha no .env: OCI_USER_OCID, OCI_TENANCY_OCID, OCI_FINGERPRINT, OCI_KEY_FILE, OCI_NAMESPACE"
        ),
    ):
        resultado = executar_persistencia_triagem(
            documento_id="DOC-OBRIG-01",
            nome_arquivo="laudo.pdf",
            conteudo_original_bytes=b"%PDF-1.4",
            dados_triagem_json={"status": "PROCESSADO", "documento_id": "DOC-OBRIG-01"},
            caminho_resultado_alvo="processados/DOC-OBRIG-01/resultado.json",
            storage=None,
            forcar_simulado=False,
        )

    assert resultado["status_backup"] == "falha"
    assert resultado["modo_simulacao"] is False
    assert resultado["caminho_objeto"] is None
    assert resultado["erro"] == MENSAGEM_PUBLICA_FALHA_OCI
    assert "OCI_USER_OCID" not in resultado["erro"]


def test_persistencia_oci_credenciais_parciais_sem_user_e_sem_key_file_retorna_falha_sanitizada(caplog):
    """Com OCI_OBRIGATORIO=false, se faltarem OCI_USER_OCID e OCI_KEY_FILE mas outros campos existirem, retorna falha."""
    with caplog.at_level(logging.ERROR, logger="mediflow.app.oci_persistence"):
        with patch(
            "src.storage.oci_storage.OCIStorage.das_configuracoes",
            side_effect=ValueError("Preencha no .env: OCI_USER_OCID, OCI_KEY_FILE"),
        ):
            resultado = executar_persistencia_triagem(
                documento_id="DOC-PARCIAL-02",
                nome_arquivo="laudo.pdf",
                conteudo_original_bytes=b"%PDF-1.4",
                dados_triagem_json={"status": "PROCESSADO", "documento_id": "DOC-PARCIAL-02"},
                caminho_resultado_alvo="processados/DOC-PARCIAL-02/resultado.json",
                storage=None,
                forcar_simulado=False,
            )

    assert resultado["status_backup"] == "falha"
    assert resultado["modo_simulacao"] is False
    assert resultado["caminho_objeto"] is None
    assert resultado["erro"] == MENSAGEM_PUBLICA_FALHA_OCI
    assert "OCI_USER_OCID" not in resultado["erro"]
    assert "OCI_KEY_FILE" not in resultado["erro"]
    assert "OCI_USER_OCID" in caplog.text


def test_persistencia_oci_chave_inexistente_ou_config_parcial_retorna_falha_sanitizada(caplog):
    """Arquivo de chave ausente ou configuração parcial do OCI resulta em falha sanitizada, não em simulado."""
    with caplog.at_level(logging.ERROR, logger="mediflow.app.oci_persistence"):
        with patch(
            "src.storage.oci_storage.OCIStorage.das_configuracoes",
            side_effect=FileNotFoundError("O arquivo indicado em OCI_KEY_FILE nao existe."),
        ):
            res_chave = executar_persistencia_triagem(
                documento_id="DOC-KEY-ERR",
                nome_arquivo="laudo.pdf",
                conteudo_original_bytes=b"%PDF-1.4",
                dados_triagem_json={"status": "PROCESSADO", "documento_id": "DOC-KEY-ERR"},
                caminho_resultado_alvo="processados/DOC-KEY-ERR/resultado.json",
                storage=None,
                forcar_simulado=False,
            )

        with patch(
            "src.storage.oci_storage.OCIStorage.das_configuracoes",
            side_effect=ValueError("Preencha no .env: OCI_NAMESPACE"),
        ):
            res_parcial = executar_persistencia_triagem(
                documento_id="DOC-PARCIAL-ERR",
                nome_arquivo="laudo.pdf",
                conteudo_original_bytes=b"%PDF-1.4",
                dados_triagem_json={"status": "PROCESSADO", "documento_id": "DOC-PARCIAL-ERR"},
                caminho_resultado_alvo="processados/DOC-PARCIAL-ERR/resultado.json",
                storage=None,
                forcar_simulado=False,
            )

    for res in (res_chave, res_parcial):
        assert res["status_backup"] == "falha"
        assert res["modo_simulacao"] is False
        assert res["caminho_objeto"] is None
        assert res["erro"] == MENSAGEM_PUBLICA_FALHA_OCI
        assert "OCI_KEY_FILE" not in res["erro"]
        assert "OCI_NAMESPACE" not in res["erro"]
    assert "OCI_KEY_FILE" in caplog.text

