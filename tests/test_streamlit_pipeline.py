"""
Testa a conexão usada pela tela.

Não chama Gemini, OCI ou servidor reais.
"""

import json
import socket
from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from src.app.triage_pipeline import (
    processar_documento_com_agente,
)
from src.schemas import (
    ClassificacaoClinica,
    DadosExtraidos,
)


@pytest.fixture(autouse=True)
def bloquear_rede(monkeypatch):
    def bloquear(*args, **kwargs):
        raise AssertionError(
            "Rede bloqueada neste teste"
        )

    monkeypatch.setattr(
        socket.socket,
        "connect",
        bloquear,
    )
    monkeypatch.setattr(
        socket.socket,
        "connect_ex",
        bloquear,
    )


def preparar(arquivo):
    pasta = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "samples"
        / "extracao_workflow"
    )

    exemplo = json.loads(
        (pasta / arquivo).read_text(
            encoding="utf-8"
        )
    )

    servico = Mock()

    servico.classificar_documento.return_value = (
        ClassificacaoClinica.model_validate(
            exemplo["classificacao"]
        )
    )

    servico.extrair_dados_clinicos_envelope.return_value = {
        "dados_clinicos": (
            DadosExtraidos.model_validate(
                exemplo["dados_extraidos"]
            )
        ),
        "urgencia": (
            exemplo["dados_extraidos"]["urgencia"]
        ),
        **exemplo["qualidade"],
    }

    return exemplo, servico


@pytest.mark.parametrize(
    "arquivo,revisao,destinos",
    [
        (
            "01_rotina.json",
            False,
            ["PRONTUARIO_ELETRONICO"],
        ),
        (
            "02_urgencia_com_campo_incerto.json",
            True,
            [
                "FILA_URGENCIA_MEDICA",
                "FILA_REVISAO_HUMANA",
            ],
        ),
        (
            "03_urgencia_indeterminada.json",
            True,
            ["FILA_REVISAO_HUMANA"],
        ),
        (
            "04_conflito_baixo.json",
            False,
            ["PRONTUARIO_ELETRONICO"],
        ),
    ],
)
def test_pipeline_preserva_sinais(
    arquivo,
    revisao,
    destinos,
):
    exemplo, servico = preparar(arquivo)

    resultado = processar_documento_com_agente(
        servico=servico,
        documento_id=exemplo["documento_id"],
        conteudo_texto="Documento fictício",
        conteudo_bytes=b"ficticio",
        mime_type="text/plain",
        limiar=0.85,
    )

    estado = resultado["estado_workflow"]

    assert (
        estado["decisao"].requer_auditoria_humana
        is revisao
    )

    assert [
        destino.value
        for destino in estado["decisao"].destinos
    ] == destinos

    assert set(
        exemplo["qualidade"]["campos_incertos"]
    ).issubset(
        estado["qualidade"].campos_incertos
    )

    assert [
        conflito.model_dump(mode="json")
        for conflito in estado["qualidade"].conflitos
    ] == exemplo["qualidade"]["conflitos"]

    argumentos = {
        "conteudo_texto": "Documento fictício",
        "conteudo_bytes": b"ficticio",
        "mime_type": "text/plain",
    }

    servico.classificar_documento.assert_called_once_with(
        **argumentos
    )

    servico.extrair_dados_clinicos_envelope.assert_called_once_with(
        **argumentos
    )

    # O caminho novo não utiliza o método antigo.
    servico.extrair_dados_clinicos.assert_not_called()

    assert "armazenamento_oci" not in estado


def test_pipeline_aplica_limiar_da_tela():
    exemplo, servico = preparar(
        "01_rotina.json"
    )

    resultado = processar_documento_com_agente(
        servico=servico,
        documento_id=exemplo["documento_id"],
        limiar=0.95,
    )

    estado = resultado["estado_workflow"]

    assert (
        estado["qualidade"].limiar_aplicado
        == 0.95
    )
    assert (
        estado["decisao"].requer_auditoria_humana
    )


def test_pipeline_rejeita_conflito_invalido():
    _, servico = preparar("01_rotina.json")

    envelope = (
        servico.extrair_dados_clinicos_envelope
        .return_value
    )
    envelope["conflitos"] = ["sem estrutura"]

    with pytest.raises(ValidationError):
        processar_documento_com_agente(
            servico=servico,
            documento_id="DOC-INVALIDO",
            limiar=0.85,
        )