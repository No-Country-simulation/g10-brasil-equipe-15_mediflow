"""
Testa envelope -> entrada -> grafo.

Reutiliza os exemplos existentes.
Não chama Gemini, API ou OCI.
"""

from copy import deepcopy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.schemas import (
    ClassificacaoClinica,
    DadosExtraidos,
)
from src.workflow.extraction_adapter import (
    entrada_do_envelope,
)
from src.workflow.graph import criar_grafo
from src.workflow.state import EntradaWorkflow


EXEMPLOS = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "samples"
    / "extracao_workflow"
)


def carregar(arquivo="01_rotina.json"):
    payload = json.loads(
        (EXEMPLOS / arquivo).read_text(
            encoding="utf-8"
        )
    )

    envelope = {
        "dados_clinicos": payload["dados_extraidos"],
        "urgencia": payload["dados_extraidos"]["urgencia"],
        "campos_incertos": (
            payload["qualidade"]["campos_incertos"]
        ),
        "conflitos": payload["qualidade"]["conflitos"],
    }

    return payload, envelope


def adaptar(payload, envelope, limiar=0.85):
    return entrada_do_envelope(
        envelope,
        documento_id=payload["documento_id"],
        classificacao=payload["classificacao"],
        limiar=limiar,
    )


@pytest.mark.parametrize(
    "arquivo",
    [
        "01_rotina.json",
        "02_urgencia_com_campo_incerto.json",
        "03_urgencia_indeterminada.json",
        "04_conflito_baixo.json",
    ],
)
def test_envelope_reproduz_entrada_e_decisao_dos_exemplos(
    arquivo,
):
    payload, envelope = carregar(arquivo)
    original = deepcopy(envelope)

    entrada = adaptar(payload, envelope)

    referencia = EntradaWorkflow.de_extracao(
        payload,
        limiar=0.85,
    )

    assert entrada.model_dump(
        mode="json"
    ) == referencia.model_dump(mode="json")

    grafo = criar_grafo()

    resultado = grafo.invoke(
        {"entrada": entrada}
    )

    esperado = grafo.invoke(
        {"entrada": referencia}
    )

    for bloco in ("qualidade", "decisao"):
        assert resultado[bloco].model_dump(
            mode="json"
        ) == esperado[bloco].model_dump(mode="json")

    assert envelope == original
    assert "armazenamento_oci" not in resultado


def test_aceita_modelos_oficiais_sem_modificar_objetos():
    payload, envelope = carregar()

    dados = DadosExtraidos.model_validate(
        envelope["dados_clinicos"]
    )

    classificacao = ClassificacaoClinica.model_validate(
        payload["classificacao"]
    )

    antes = dados.model_dump(mode="json")

    envelope["dados_clinicos"] = dados

    entrada = entrada_do_envelope(
        envelope,
        documento_id=payload["documento_id"],
        classificacao=classificacao,
        limiar=0.85,
    )

    assert entrada.dados_extraidos.model_dump(
        mode="json"
    ) == antes

    assert dados.model_dump(mode="json") == antes

    assert entrada.dados_extraidos is not dados


def test_urgencia_extraida_nao_e_substituida_pela_classificacao():
    payload, envelope = carregar()

    envelope["urgencia"] = "SIM"
    envelope["dados_clinicos"]["urgencia"] = "SIM"

    assert (
        payload["classificacao"]["nivel_prioridade"]
        == "ROTINA"
    )

    entrada = adaptar(payload, envelope)

    assert entrada.urgencia == "SIM"

    resultado = criar_grafo().invoke(
        {"entrada": entrada}
    )

    destinos = [
        destino.value
        for destino in resultado["decisao"].destinos
    ]

    assert "FILA_URGENCIA_MEDICA" in destinos


def test_limiar_vem_da_aplicacao_e_nao_do_envelope():
    payload, envelope = carregar()

    # Uma configuração presente no envelope não deve
    # substituir o limiar fornecido pela aplicação.
    envelope["limiar"] = 0.01

    entrada = adaptar(
        payload,
        envelope,
        limiar=0.97,
    )

    assert entrada.limiar == 0.97

    resultado = criar_grafo().invoke(
        {"entrada": entrada}
    )

    assert (
        resultado["qualidade"].limiar_aplicado
        == 0.97
    )

    assert resultado["decisao"].requer_auditoria_humana


@pytest.mark.parametrize(
    "campo",
    [
        "dados_clinicos",
        "urgencia",
        "campos_incertos",
        "conflitos",
    ],
)
def test_envelope_incompleto_nao_fabrica_sinais(campo):
    payload, envelope = carregar()

    del envelope[campo]

    with pytest.raises(
        ValueError,
        match="Envelope incompleto",
    ):
        adaptar(payload, envelope)


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("urgencia", "TALVEZ"),
        ("urgencia", None),
        ("campos_incertos", None),
        ("conflitos", None),
        ("dados_clinicos", None),
        (
            "conflitos",
            [
                {
                    "tipo": "TESTE",
                    "gravidade": "DESCONHECIDA",
                }
            ],
        ),
    ],
)
def test_envelope_invalido_nao_e_corrigido_silenciosamente(
    campo,
    valor,
):
    payload, envelope = carregar()

    envelope[campo] = valor

    with pytest.raises(
        (ValueError, ValidationError)
    ):
        adaptar(payload, envelope)


def test_urgencias_contraditorias_sao_rejeitadas_pelo_workflow():
    payload, envelope = carregar()

    # O exemplo informa NAO nos dados clínicos.
    # Alteramos somente o sinal externo para criar
    # uma contradição que o workflow deve rejeitar.
    envelope["urgencia"] = "SIM"

    with pytest.raises(
        ValueError,
        match="Urgência divergente",
    ):
        adaptar(payload, envelope)