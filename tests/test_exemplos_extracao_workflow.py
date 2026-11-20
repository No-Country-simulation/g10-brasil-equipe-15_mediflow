"""
Testa exemplos de extração normalizada usando o adaptador
e o grafo existentes.

Não chama Gemini, API ou OCI.
"""

import json
from pathlib import Path

import pytest

from src.workflow.graph import criar_grafo
from src.workflow.state import EntradaWorkflow


PASTA_EXEMPLOS = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "samples"
    / "extracao_workflow"
)


@pytest.mark.parametrize(
    "arquivo,score_extracao,score_combinado,destinos,revisao",
    [
        pytest.param(
            "01_rotina.json",
            1.0,
            0.93,
            ["PRONTUARIO_ELETRONICO"],
            False,
            id="rotina",
        ),
        pytest.param(
            "02_urgencia_com_campo_incerto.json",
            0.90,
            0.90,
            [
                "FILA_URGENCIA_MEDICA",
                "FILA_REVISAO_HUMANA",
            ],
            True,
            id="urgencia-com-incerteza",
        ),
        pytest.param(
            "03_urgencia_indeterminada.json",
            0.90,
            0.90,
            ["FILA_REVISAO_HUMANA"],
            True,
            id="urgencia-indeterminada",
        ),
        pytest.param(
            "04_conflito_baixo.json",
            0.90,
            0.90,
            ["PRONTUARIO_ELETRONICO"],
            False,
            id="conflito-baixo",
        ),
    ],
)
def test_exemplo_adaptado_ao_workflow(
    arquivo,
    score_extracao,
    score_combinado,
    destinos,
    revisao,
):
    # Carrega os dados fictícios do exemplo.
    payload = json.loads(
        (PASTA_EXEMPLOS / arquivo).read_text(
            encoding="utf-8"
        )
    )
    sinais = payload["qualidade"]

    # Os exemplos fornecem sinais, sem cálculos
    # ou decisões prontos.
    assert "score_extracao" not in sinais
    assert "score_combinado" not in sinais
    assert "limiar_aplicado" not in sinais
    assert "decisao_roteamento" not in payload

    # Reutiliza o adaptador oficial.
    # O limiar é fornecido pelo teste, não pelo documento.
    entrada = EntradaWorkflow.de_extracao(
        payload,
        limiar=0.85,
    )

    # Reutiliza o grafo existente.
    resultado = criar_grafo().invoke(
        {"entrada": entrada}
    )

    qualidade = resultado["qualidade"]
    decisao = resultado["decisao"]

    # Confere a preservação da identificação e da urgência.
    assert entrada.documento_id == payload["documento_id"]
    assert (
        entrada.urgencia
        == payload["dados_extraidos"]["urgencia"]
    )

    # Confere os resultados calculados pelo agente.
    assert qualidade.score_classificacao == pytest.approx(
        payload["classificacao"]["score_classificacao"]
    )
    assert qualidade.score_extracao == pytest.approx(
        score_extracao
    )
    assert qualidade.score_combinado == pytest.approx(
        score_combinado
    )
    assert qualidade.limiar_aplicado == 0.85

    # O agente pode acrescentar sinais de incerteza,
    # mas deve preservar os recebidos.
    assert set(sinais["campos_incertos"]).issubset(
        qualidade.campos_incertos
    )

    assert [
        conflito.model_dump(mode="json")
        for conflito in qualidade.conflitos
    ] == sinais["conflitos"]

    # Confere destinos e necessidade de revisão.
    assert [
        destino.value
        for destino in decisao.destinos
    ] == destinos

    assert decisao.requer_auditoria_humana is revisao
    assert bool(qualidade.motivos_revisao) is revisao
    assert decisao.justificativa.strip()

    # A decisão interna não confirma armazenamento.
    assert decisao.etapa == "DECISAO_CALCULADA"
    assert "armazenamento_oci" not in resultado