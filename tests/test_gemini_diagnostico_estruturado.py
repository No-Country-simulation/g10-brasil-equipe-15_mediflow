"""Regressões de diagnóstico e idade, sem chamadas reais ao Gemini."""

from copy import deepcopy
import json
from unittest.mock import patch

import pytest
from pydantic import ValidationError

import src.services.gemini_service as modulo


@pytest.mark.parametrize(
    ("payload", "diagnostico", "cid"),
    [
        (
            {
                "diagnostico": {
                    "descricao": "Descrição fictícia.",
                    "cid_extraido": "J06.9",
                }
            },
            "Descrição fictícia.",
            "J06.9",
        ),
        (
            {
                "diagnostico_principal": {
                    "descricao": "Descrição fictícia.",
                }
            },
            "Descrição fictícia.",
            None,
        ),
        (
            {
                "diagnostico": {
                    "descricao": None,
                    "cid_extraido": None,
                }
            },
            None,
            None,
        ),
        (
            {
                "diagnostico": {
                    "descricao": "Descrição fictícia.",
                    "cid_extraido": "J06.9",
                },
                "cid": "J06.9",
            },
            "Descrição fictícia.",
            "J06.9",
        ),
    ],
    ids=[
        "objeto-com-cid",
        "alias-sem-cid",
        "nulos",
        "cid-coincidente",
    ],
)
def test_normaliza_diagnostico_sem_perder_cid(
    payload, diagnostico, cid
):
    original = deepcopy(payload)

    normalizado = modulo.normalizar_payload_extracao(payload)
    dados = modulo.DadosClinicosExtraidos.model_validate(normalizado)

    assert dados.diagnostico == diagnostico
    assert dados.cid == cid
    assert payload == original


@pytest.mark.parametrize(
    "payload",
    [
        {
            "diagnostico": {
                "descricao": "Descrição fictícia.",
                "cid_extraido": "J06.9",
            },
            "cid": "M54.5",
        },
        {
            "diagnostico": {
                "descricao": "Descrição fictícia.",
                "informacao_adicional": "Não pode ser descartada.",
            }
        },
        {
            "diagnostico": {
                "descricao": {"texto": "Formato desconhecido."},
            }
        },
        {
            "diagnostico": {
                "descricao": "Descrição fictícia.",
                "cid_extraido": ["J06.9"],
            }
        },
        {
            "diagnostico": {
                "descricao": "Primeira descrição.",
            },
            "diagnostico_principal": "Descrição diferente.",
        },
    ],
    ids=[
        "cid-conflitante",
        "campo-desconhecido",
        "descricao-como-objeto",
        "cid-como-lista",
        "diagnosticos-conflitantes",
    ],
)
def test_rejeita_estrutura_ambigua_sem_modificar_original(payload):
    original = deepcopy(payload)

    with pytest.raises(ValueError):
        modulo.normalizar_payload_extracao(payload)

    assert payload == original


def test_preserva_payload_textual_e_sinais():
    payload = {
        "diagnostico": "Descrição fictícia.",
        "cid": None,
        "urgencia": "SIM",
        "campos_incertos": ["paciente.idade"],
        "conflitos": [
            {
                "tipo": "dados_divergentes",
                "gravidade": "ALTA",
                "descricao": "Conflito fictício.",
                "campos": ["paciente.idade"],
            }
        ],
    }

    assert modulo.normalizar_payload_extracao(payload) == payload


def test_servico_extrai_objeto_preservando_dados_e_sinais():
    payload = {
        "paciente": {
            "nome": "Pessoa Fictícia",
            "idade": 29,
        },
        "diagnostico": {
            "descricao": "Descrição fictícia.",
            "cid_extraido": "J06.9",
        },
        "urgencia": "NAO",
        "score_confianca_extracao": 0.91,
        "campos_incertos": ["medico.nome"],
        "conflitos": [],
    }

    with patch.object(modulo, "genai") as sdk:
        modelo = sdk.GenerativeModel.return_value
        modelo.generate_content.return_value.text = json.dumps(payload)

        servico = modulo.GeminiService(
            api_key="chave-ficticia",
            model_name="modelo-ficticio",
        )

        with patch.object(
            servico,
            "_fallback_envelope",
            side_effect=AssertionError("Não deveria usar fallback."),
        ):
            envelope = servico.extrair_dados_clinicos_envelope(
                conteudo_texto="Documento exclusivamente fictício."
            )

        dados = envelope["dados_clinicos"]

        assert dados.paciente.idade == 29
        assert dados.diagnostico == "Descrição fictícia."
        assert dados.cid == "J06.9"
        assert envelope["urgencia"] == "NAO"
        assert envelope["campos_incertos"] == ["medico.nome"]
        assert envelope["conflitos"] == []

        modelo.generate_content.assert_called_once()


def test_servico_nao_declara_extracao_valida_com_cid_conflitante():
    payload = {
        "diagnostico": {
            "descricao": "Descrição fictícia.",
            "cid_extraido": "J06.9",
        },
        "cid": "M54.5",
    }

    with patch.object(modulo, "genai") as sdk:
        modelo = sdk.GenerativeModel.return_value
        modelo.generate_content.return_value.text = json.dumps(payload)

        servico = modulo.GeminiService(api_key="chave-ficticia")

        envelope = servico.extrair_dados_clinicos_envelope(
            conteudo_texto="Documento exclusivamente fictício."
        )

        dados = envelope["dados_clinicos"]

        assert dados.score_confianca_extracao == 0.0
        assert dados.diagnostico is None
        assert dados.cid is None
        assert envelope["urgencia"] == "INDETERMINADO"


@pytest.mark.parametrize(
    ("idade_recebida", "idade_esperada"),
    [
        ("29", 29),
        ("29 anos", 29),
        (" 29 ANOS ", 29),
        ("1 ano", 1),
    ],
    ids=[
        "numero-textual",
        "idade-com-anos",
        "espacos-e-maiusculas",
        "ano-singular",
    ],
)
def test_normaliza_idade_textual_inequivoca(
    idade_recebida, idade_esperada
):
    payload = {
        "paciente": {
            "nome": "Pessoa Fictícia",
            "idade": idade_recebida,
        },
        "diagnostico": {
            "descricao": "Descrição fictícia.",
            "cid_extraido": "J06.9",
        },
    }
    original = deepcopy(payload)

    normalizado = modulo.normalizar_payload_extracao(payload)
    dados = modulo.DadosClinicosExtraidos.model_validate(normalizado)

    assert dados.paciente.idade == idade_esperada
    assert dados.diagnostico == "Descrição fictícia."
    assert dados.cid == "J06.9"
    assert payload == original


@pytest.mark.parametrize(
    "idade",
    [
        "29 ou 39 anos",
        "4 meses",
        "-5",
        "29.5 anos",
        "aproximadamente 29 anos",
    ],
    ids=[
        "idades-alternativas",
        "idade-em-meses",
        "numero-negativo",
        "numero-decimal",
        "idade-aproximada",
    ],
)
def test_rejeita_idade_textual_ambigua_sem_escolher_numero(idade):
    payload = {"paciente": {"idade": idade}}
    original = deepcopy(payload)

    with pytest.raises(ValueError):
        modulo.normalizar_payload_extracao(payload)

    assert payload == original


@pytest.mark.parametrize(
    "idade",
    [29, None],
    ids=["idade-inteira", "idade-nula"],
)
def test_preserva_idade_numerica_ou_ausente(idade):
    payload = {"paciente": {"idade": idade}}

    normalizado = modulo.normalizar_payload_extracao(payload)
    dados = modulo.DadosClinicosExtraidos.model_validate(normalizado)

    assert dados.paciente.idade == idade


def test_idade_fora_da_faixa_continua_rejeitada_pelo_schema():
    normalizado = modulo.normalizar_payload_extracao(
        {"paciente": {"idade": "121 anos"}}
    )

    with pytest.raises(ValidationError):
        modulo.DadosClinicosExtraidos.model_validate(normalizado)
