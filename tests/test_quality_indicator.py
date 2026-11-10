"""
Testes TDD para a camada de cálculo e segregação de indicadores de qualidade e roteamento.

Garante conformidade com os contratos Pydantic 'Qualidade' e 'DecisaoRoteamento'
e valida a regra de que o limiar é dinâmico (limiar_aplicado) e que a qualidade matemática
não se confunde com a decisão clínica de auditoria humana.
"""
from types import SimpleNamespace
import pytest

from src.schemas import Qualidade, DecisaoRoteamento, Destino
from src.app.quality_indicator import (
    calcular_indicadores_qualidade_e_roteamento,
    IndicadoresQualidadeRoteamento,
)


def test_rotina_score_alto_dispensa_revisao():
    """Score 0.96 >= 0.85 sem pendências deve dispensar revisão médica com aprovação direta."""
    qualidade = Qualidade(
        score_combinado=0.96,
        score_classificacao=0.96,
        score_extracao=0.98,
        limiar_aplicado=0.85,
    )
    decisao = DecisaoRoteamento(
        destinos=[Destino.PRONTUARIO_ELETRONICO],
        requer_auditoria_humana=False,
        justificativa_roteamento="Critérios de rotina aprovados.",
    )

    indicador = calcular_indicadores_qualidade_e_roteamento(
        qualidade_wf=qualidade,
        decisao_wf=decisao,
        foi_auditado=False,
    )

    assert isinstance(indicador, IndicadoresQualidadeRoteamento)
    assert indicador.limiar_aplicado == 0.85
    assert indicador.score_combinado == 0.96
    assert indicador.atingiu_limiar is True
    assert "≥ 0.85" in indicador.delta_score
    assert indicador.delta_score_cor == "normal"
    assert indicador.revisao_humana_status == "Dispensada"
    assert indicador.revisao_humana_motivo == "Aprovação Direta"
    assert indicador.revisao_humana_cor == "normal"
    assert indicador.requer_atencao_mista is False
    assert indicador.aviso_misto is None


def test_urgencia_score_alto_exige_revisao_por_regra_clinica():
    """Score 0.98 >= 0.85 em caso crítico (TEP) atinge limiar matemático, mas exige revisão humana por regra clínica."""
    qualidade = Qualidade(
        score_combinado=0.98,
        score_classificacao=0.99,
        score_extracao=0.98,
        limiar_aplicado=0.85,
    )
    decisao = DecisaoRoteamento(
        destinos=[Destino.FILA_URGENCIA_MEDICA, Destino.FILA_REVISAO_HUMANA],
        requer_auditoria_humana=True,
        justificativa_roteamento="Caso crítico com notificação hospitalar e auditoria simultânea.",
    )

    indicador = calcular_indicadores_qualidade_e_roteamento(
        qualidade_wf=qualidade,
        decisao_wf=decisao,
        foi_auditado=False,
    )

    assert indicador.atingiu_limiar is True
    assert "≥ 0.85" in indicador.delta_score
    assert indicador.revisao_humana_status == "Exigida"
    assert indicador.revisao_humana_motivo == "Por Regra Clínica"
    assert indicador.revisao_humana_cor == "inverse"
    # Ponto focal do usuário: caso misto evidenciado com clareza
    assert indicador.requer_atencao_mista is True
    assert indicador.aviso_misto is not None
    assert "0.98" in indicador.aviso_misto
    assert "0.85" in indicador.aviso_misto
    assert "revisão humana" in indicador.aviso_misto.lower()


def test_ambiguo_score_baixo_exige_revisao_por_score():
    """Score 0.65 < 0.85 deve marcar score abaixo do limiar e revisão exigida por score insuficiente."""
    qualidade = Qualidade(
        score_combinado=0.65,
        score_classificacao=0.80,
        score_extracao=0.65,
        limiar_aplicado=0.85,
    )
    decisao = DecisaoRoteamento(
        destinos=[Destino.FILA_REVISAO_HUMANA],
        requer_auditoria_humana=True,
        justificativa_roteamento="Score abaixo do limiar oficial.",
    )

    indicador = calcular_indicadores_qualidade_e_roteamento(
        qualidade_wf=qualidade,
        decisao_wf=decisao,
        foi_auditado=False,
    )

    assert indicador.atingiu_limiar is False
    assert "< 0.85" in indicador.delta_score
    assert indicador.delta_score_cor == "inverse"
    assert indicador.revisao_humana_status == "Exigida"
    assert indicador.revisao_humana_motivo == "Score Insuficiente"
    assert indicador.revisao_humana_cor == "inverse"
    assert indicador.requer_atencao_mista is False


def test_limiar_customizado_dinamico():
    """Se o motor aplicar limiar diferente (ex: 0.90), deve respeitar o limiar dinamicamente sem usar 0.85."""
    qualidade = Qualidade(
        score_combinado=0.88,
        score_classificacao=0.90,
        score_extracao=0.87,
        limiar_aplicado=0.90,
    )
    decisao = DecisaoRoteamento(
        destinos=[Destino.FILA_REVISAO_HUMANA],
        requer_auditoria_humana=True,
        justificativa_roteamento="Abaixo do limiar customizado.",
    )

    indicador = calcular_indicadores_qualidade_e_roteamento(
        qualidade_wf=qualidade,
        decisao_wf=decisao,
        foi_auditado=False,
    )

    assert indicador.limiar_aplicado == 0.90
    assert indicador.atingiu_limiar is False
    assert "< 0.90" in indicador.delta_score
    assert "0.85" not in indicador.delta_score


def test_pos_auditoria_homologada():
    """Quando o médico homologa no HiTL, o status da revisão médica deve ser 'Homologada'."""
    qualidade = Qualidade(
        score_combinado=0.65,
        score_classificacao=0.80,
        score_extracao=0.65,
        limiar_aplicado=0.85,
    )
    decisao = DecisaoRoteamento(
        destinos=[Destino.FILA_REVISAO_HUMANA],
        requer_auditoria_humana=True,
        justificativa_roteamento="Documento retido para auditoria.",
    )

    indicador = calcular_indicadores_qualidade_e_roteamento(
        qualidade_wf=qualidade,
        decisao_wf=decisao,
        foi_auditado=True,
    )

    assert indicador.revisao_humana_status == "Homologada"
    assert indicador.revisao_humana_motivo == "Aprovado HiTL"
    assert indicador.revisao_humana_cor == "normal"
    assert indicador.requer_atencao_mista is False

