"""
Testes TDD para a camada de persistência OCI do Streamlit.

Verifica que o seam 'executar_persistencia_triagem' reporta fielmente:
1. Sucesso real de gravação com ETag quando OCI confirma HTTP 200/201.
2. Falha real com mensagem/código da Oracle quando OCI lança ServiceError (ex: 412 IfNoneMatchFailed).
3. Modo simulado transparente quando OCI não está configurado ou em modo demo.
"""
from types import SimpleNamespace
from unittest.mock import Mock, patch
import json
import pytest
import oci

from src.app.oci_persistence import executar_persistencia_triagem


def test_persistencia_oci_sucesso_retorna_status_e_etag():
    """Se o conector OCI grava o objeto com sucesso, deve retornar status_backup='sucesso' e ETag real."""
    storage_mock = Mock()
    storage_mock.bucket = "mediflow-documentos"
    storage_mock.enviar_bytes.return_value = {
        "bucket": "mediflow-documentos",
        "caminho_objeto": "processados/DOC-001/resultado.json",
        "etag": "etag-real-12345",
        "status_backup": "sucesso",
    }

    resultado = executar_persistencia_triagem(
        documento_id="DOC-001",
        nome_arquivo="receita.txt",
        conteudo_original_bytes=b"Conteudo da receita",
        dados_triagem_json={"status": "PROCESSADO", "documento_id": "DOC-001"},
        caminho_resultado_alvo="processados/DOC-001/resultado.json",
        storage=storage_mock,
        forcar_simulado=False,
    )

    assert resultado["status_backup"] == "sucesso"
    assert resultado["modo_simulacao"] is False
    assert resultado["etag"] == "etag-real-12345"
    assert resultado["bucket"] == "mediflow-documentos"
    assert resultado["caminho_objeto"] == "processados/DOC-001/resultado.json"
    assert "erro" not in resultado or resultado["erro"] is None
    assert "gravado com sucesso" in resultado["evento_linha_do_tempo"].lower()
    assert storage_mock.enviar_bytes.call_count >= 1


def test_persistencia_oci_falha_412_retorna_status_falha_com_detalhe():
    """Se o OCI rejeitar com 412 IfNoneMatchFailed (ou qualquer ServiceError), deve retornar status_backup='falha'."""
    storage_mock = Mock()
    storage_mock.bucket = "mediflow-documentos"
    storage_mock.enviar_bytes.side_effect = oci.exceptions.ServiceError(
        status=412,
        code="IfNoneMatchFailed",
        headers={"opc-request-id": "req-gru-412"},
        message="The current entity tag did not match the if-none-match condition.",
    )

    resultado = executar_persistencia_triagem(
        documento_id="DOC-001",
        nome_arquivo="receita.txt",
        conteudo_original_bytes=b"Conteudo da receita",
        dados_triagem_json={"status": "PROCESSADO", "documento_id": "DOC-001"},
        caminho_resultado_alvo="processados/DOC-001/resultado.json",
        storage=storage_mock,
        forcar_simulado=False,
    )

    # Regra fundamental: Falha NUNCA vira sucesso nem silencia erro
    assert resultado["status_backup"] == "falha"
    assert resultado["modo_simulacao"] is False
    assert resultado["etag"] is None
    assert "412" in resultado["erro"]
    assert "IfNoneMatchFailed" in resultado["erro"]
    assert "req-gru-412" in resultado["erro"]
    assert "falha" in resultado["evento_linha_do_tempo"].lower()


def test_persistencia_oci_sem_credenciais_retorna_modo_simulado():
    """Quando o OCI não está configurado no .env, deve sinalizar modo_simulacao=True e status_backup='simulado'."""
    with patch("src.storage.oci_storage.OCIStorage.das_configuracoes", side_effect=ValueError("Preencha no .env")):
        resultado = executar_persistencia_triagem(
            documento_id="DOC-002",
            nome_arquivo="laudo.pdf",
            conteudo_original_bytes=b"%PDF-1.4",
            dados_triagem_json={"status": "EM_REVISAO", "documento_id": "DOC-002"},
            caminho_resultado_alvo="auditoria/DOC-002.json",
            storage=None,  # Sem storage injetado, força resolução das configurações
            forcar_simulado=False,
        )

        assert resultado["status_backup"] == "simulado"
        assert resultado["modo_simulacao"] is True
        assert resultado["etag"] is None
        assert "simulad" in resultado["evento_linha_do_tempo"].lower() or "local" in resultado["evento_linha_do_tempo"].lower()
        assert "não configurado" in resultado["detalhes"].lower() or "local" in resultado["detalhes"].lower()


def test_persistencia_oci_forcar_simulado_cenario_demo():
    """Para cenários oficiais demo do edital, deve permanecer em modo simulado sem acessar nuvem."""
    storage_mock = Mock()

    resultado = executar_persistencia_triagem(
        documento_id="DOC-DEMO-01",
        nome_arquivo="01_rotina.pdf",
        conteudo_original_bytes=b"%PDF-1.4",
        dados_triagem_json={"status": "PROCESSADO", "documento_id": "DOC-DEMO-01"},
        caminho_resultado_alvo="processados/DOC-DEMO-01.json",
        storage=storage_mock,
        forcar_simulado=True,
    )

    assert resultado["status_backup"] == "simulado"
    assert resultado["modo_simulacao"] is True
    # Não deve ter chamado enviar_bytes do storage
    assert storage_mock.enviar_bytes.call_count == 0

