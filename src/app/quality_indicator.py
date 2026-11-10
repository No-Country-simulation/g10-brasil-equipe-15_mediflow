"""
Camada de cálculo e segregação de indicadores de qualidade e roteamento clínico.

Segrega com precisão matemática a Fórmula A3 da decisão de roteamento/auditoria humana,
em total conformidade com os contratos canônicos Pydantic.
"""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class IndicadoresQualidadeRoteamento(BaseModel):
    """Modelo Pydantic que encapsula a métrica matemática A3 e a decisão de auditoria."""
    model_config = ConfigDict(extra="ignore")

    limiar_aplicado: float = Field(..., description="Limiar dinâmico configurado no motor LangGraph")
    score_combinado: float = Field(..., ge=0.0, le=1.0)
    score_classificacao: float = Field(..., ge=0.0, le=1.0)
    score_extracao: float = Field(..., ge=0.0, le=1.0)
    atingiu_limiar: bool = Field(..., description="True se score_combinado >= limiar_aplicado")
    delta_score: str = Field(..., description="Texto do delta matemático (ex: '≥ 0.85' ou '< 0.85')")
    delta_score_cor: str = Field(default="normal", description="'normal' (verde) ou 'inverse' (vermelho)")
    revisao_humana_status: str = Field(..., description="'Dispensada', 'Exigida' ou 'Homologada'")
    revisao_humana_motivo: str = Field(..., description="Motivo explicativo do status de auditoria")
    revisao_humana_cor: str = Field(default="normal", description="'normal' (verde) ou 'inverse' (vermelho)")
    requer_atencao_mista: bool = Field(default=False, description="True quando atingiu o limiar mas exige revisão clínica")
    aviso_misto: Optional[str] = Field(None, description="Texto explicativo para o caso misto")


def calcular_indicadores_qualidade_e_roteamento(
    *,
    qualidade_wf: Any,
    decisao_wf: Any,
    foi_auditado: bool = False,
) -> IndicadoresQualidadeRoteamento:
    """
    Segrega com precisão matemática a Fórmula A3 da decisão de roteamento clínico,
    garantindo que um caso que atinge o limiar mas requer revisão humana fique evidente.
    """
    limiar_real = float(getattr(qualidade_wf, "limiar_aplicado", 0.85))
    score_comb = float(getattr(qualidade_wf, "score_combinado", 0.0))
    score_class = float(getattr(qualidade_wf, "score_classificacao", 0.0))
    score_ext = float(getattr(qualidade_wf, "score_extracao", 0.0))

    atingiu_limiar = bool(score_comb >= limiar_real)
    delta_score = f"≥ {limiar_real:.2f}" if atingiu_limiar else f"< {limiar_real:.2f}"
    delta_score_cor = "normal" if atingiu_limiar else "inverse"

    requer_auditoria = bool(getattr(decisao_wf, "requer_auditoria_humana", False))

    if foi_auditado:
        revisao_status = "Homologada"
        revisao_motivo = "Aprovado HiTL"
        revisao_cor = "normal"
        requer_mista = False
        aviso_misto = None
    elif requer_auditoria:
        revisao_status = "Exigida"
        revisao_cor = "inverse"
        if atingiu_limiar:
            revisao_motivo = "Por Regra Clínica"
            requer_mista = True
            aviso_misto = (
                f"ℹ️ **Limiar de qualidade atingido ({score_comb:.2f} ≥ {limiar_real:.2f})**, porém o "
                f"roteamento determinístico reteve o documento para **Revisão Humana** devido a critérios "
                f"clínicos determinísticos (ex: caso crítico, ausência de campo obrigatório ou conflito clínico)."
            )
        else:
            revisao_motivo = "Score Insuficiente"
            requer_mista = False
            aviso_misto = None
    else:
        revisao_status = "Dispensada"
        revisao_motivo = "Aprovação Direta"
        revisao_cor = "normal"
        requer_mista = False
        aviso_misto = None

    return IndicadoresQualidadeRoteamento(
        limiar_aplicado=limiar_real,
        score_combinado=score_comb,
        score_classificacao=score_class,
        score_extracao=score_ext,
        atingiu_limiar=atingiu_limiar,
        delta_score=delta_score,
        delta_score_cor=delta_score_cor,
        revisao_humana_status=revisao_status,
        revisao_humana_motivo=revisao_motivo,
        revisao_humana_cor=revisao_cor,
        requer_atencao_mista=requer_mista,
        aviso_misto=aviso_misto,
    )

