"""
Integração simulada:
GeminiService -> adaptador -> grafo existente.

Não chama Gemini real nem OCI.
"""

import json
import socket
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from src.workflow.extraction_adapter import (
    entrada_do_envelope,
)
from src.workflow.graph import criar_grafo


@pytest.fixture
def servico_simulado(monkeypatch):
    def bloquear_rede(*args, **kwargs):
        raise AssertionError(
            "Rede bloqueada neste teste"
        )

    monkeypatch.setattr(
        socket.socket,
        "connect",
        bloquear_rede,
    )
    monkeypatch.setattr(
        socket.socket,
        "connect_ex",
        bloquear_rede,
    )

    from src.services import gemini_service as modulo

    # Substitui o SDK inteiro antes de construir o serviço.
    sdk = Mock()
    monkeypatch.setattr(modulo, "genai", sdk)

    servico = modulo.GeminiService(
        api_key="chave-ficticia"
    )

    yield servico, sdk


@pytest.fixture
def exemplo_rotina():
    pasta = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "samples"
        / "extracao_workflow"
    )

    return json.loads(
        (pasta / "01_rotina.json").read_text(
            encoding="utf-8"
        )
    )


def obter_envelope(servico_simulado, exemplo):
    servico, sdk = servico_simulado

    # Simula o JSON bruto retornado pelo Gemini.
    # A conversão para o envelope é feita pelo serviço real.
    resposta = {
        **exemplo["dados_extraidos"],
        **exemplo["qualidade"],
    }

    modelo = sdk.GenerativeModel.return_value
    modelo.generate_content.return_value.text = (
        json.dumps(resposta)
    )

    return servico.extrair_dados_clinicos_envelope(
        "Documento fictício"
    )


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
def test_servico_envelope_adaptador_grafo(
    servico_simulado,
    arquivo,
    revisao,
    destinos,
):
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

    envelope = obter_envelope(
        servico_simulado,
        exemplo,
    )
    antes = deepcopy(envelope)

    entrada = entrada_do_envelope(
        documento_id=exemplo["documento_id"],
        classificacao=exemplo["classificacao"],
        envelope=envelope,
        limiar=0.85,
    )

    resultado = criar_grafo().invoke(
        {"entrada": entrada}
    )

    assert (
        entrada.documento_id
        == exemplo["documento_id"]
    )
    assert entrada.urgencia == envelope["urgencia"]

    # O grafo pode acrescentar incertezas, mas precisa
    # preservar os sinais recebidos do serviço.
    assert set(
        envelope["campos_incertos"]
    ).issubset(
        resultado["qualidade"].campos_incertos
    )

    assert [
        conflito.model_dump(mode="json")
        for conflito in resultado["qualidade"].conflitos
    ] == envelope["conflitos"]

    assert (
        resultado["decisao"].requer_auditoria_humana
        is revisao
    )

    assert [
        destino.value
        for destino in resultado["decisao"].destinos
    ] == destinos

    assert (
        resultado["decisao"].etapa
        == "DECISAO_CALCULADA"
    )
    assert "armazenamento_oci" not in resultado

    # O adaptador e o grafo não modificam o envelope.
    assert envelope == antes


@pytest.mark.parametrize(
    "dosagem,frequencia",
    [
        (None, "6/6h"),
        ("500mg", None),
    ],
)
def test_medicamento_preservado(
    servico_simulado,
    exemplo_rotina,
    dosagem,
    frequencia,
):
    exemplo_rotina["dados_extraidos"]["medicamentos"] = [
        {
            "nome": "Medicamento fictício",
            "dosagem": dosagem,
            "frequencia": frequencia,
        }
    ]

    envelope = obter_envelope(
        servico_simulado,
        exemplo_rotina,
    )

    entrada = entrada_do_envelope(
        documento_id="DOC-MEDICAMENTO",
        classificacao=exemplo_rotina["classificacao"],
        envelope=envelope,
        limiar=0.85,
    )

    medicamento = (
        entrada.dados_extraidos.medicamentos[0]
    )

    assert medicamento.dosagem == dosagem
    assert medicamento.frequencia == frequencia


def test_timeout_vai_para_revisao(
    servico_simulado,
    exemplo_rotina,
):
    servico, sdk = servico_simulado
    modelo = sdk.GenerativeModel.return_value

    modelo.generate_content.side_effect = TimeoutError(
        "Falha fictícia"
    )

    envelope = (
        servico.extrair_dados_clinicos_envelope(
            "Documento fictício"
        )
    )

    entrada = entrada_do_envelope(
        documento_id="DOC-FALHA-IA",
        classificacao=exemplo_rotina["classificacao"],
        envelope=envelope,
        limiar=0.85,
    )

    resultado = criar_grafo().invoke(
        {"entrada": entrada}
    )

    assert (
        entrada.dados_extraidos.diagnostico_principal
        is None
    )
    assert entrada.urgencia == "INDETERMINADO"
    assert (
        resultado["decisao"].requer_auditoria_humana
    )


@pytest.mark.parametrize(
    "alteracao",
    [
        {"urgencia": "TALVEZ"},
        {"campos_incertos": None},
        {"conflitos": ["Conflito sem estrutura"]},
    ],
)
def test_sinal_invalido_nao_e_convertido_em_lista_vazia(
    servico_simulado,
    exemplo_rotina,
    alteracao,
):
    envelope = obter_envelope(
        servico_simulado,
        exemplo_rotina,
    )
    envelope.update(alteracao)

    # Sinais inválidos não devem desaparecer
    # silenciosamente nem virar listas vazias.
    with pytest.raises(
        (ValueError, ValidationError)
    ):
        entrada_do_envelope(
            documento_id="DOC-INVALIDO",
            classificacao=exemplo_rotina["classificacao"],
            envelope=envelope,
            limiar=0.85,
        )


def test_limiar_vem_da_aplicacao(
    servico_simulado,
    exemplo_rotina,
):
    envelope = obter_envelope(
        servico_simulado,
        exemplo_rotina,
    )

    # Um valor extra recebido no envelope não pode
    # substituir a configuração da aplicação.
    envelope["limiar"] = 0.01

    entrada = entrada_do_envelope(
        documento_id="DOC-LIMIAR",
        classificacao=exemplo_rotina["classificacao"],
        envelope=envelope,
        limiar=0.95,
    )

    resultado = criar_grafo().invoke(
        {"entrada": entrada}
    )

    assert (
        resultado["qualidade"].limiar_aplicado
        == 0.95
    )
    assert (
        resultado["decisao"].requer_auditoria_humana
    )