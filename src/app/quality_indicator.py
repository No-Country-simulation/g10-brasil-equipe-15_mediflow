"""
Camada de cálculo e segregação de indicadores de qualidade e montagem canônica de triagem.

Segrega com precisão matemática o comparador de limiar (R5) e a Fórmula A3 da decisão
determinística de auditoria humana (RN-08 / R1-R8), além de construir instâncias íntegras
de TriagemMediFlow preservando urgência extraída, exames laboratoriais (A6) e status OCI.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.app.oci_persistence import MENSAGEM_PUBLICA_FALHA_OCI
from src.schemas import (
    ArmazenamentoOCI,
    Classificacao,
    CodigoErro,
    Conflito,
    DadosExtraidos,
    DecisaoRoteamento,
    Destino,
    ErroProcessamento,
    Gravidade,
    NivelPrioridade,
    Notificacao,
    Qualidade,
    StatusTriagem,
    TriagemMediFlow,
    Urgencia,
)


class IndicadoresQualidadeRoteamento(BaseModel):
    """Modelo Pydantic que encapsula as métricas de score (R5/A3) e a decisão de revisão."""

    model_config = ConfigDict(extra="ignore")

    limiar_aplicado: float = Field(..., description="Limiar dinâmico configurado no motor LangGraph")
    score_combinado: float = Field(..., ge=0.0, le=1.0)
    score_classificacao: float = Field(..., ge=0.0, le=1.0)
    score_extracao: float = Field(..., ge=0.0, le=1.0)
    atingiu_limiar: bool = Field(..., description="True se score_combinado >= limiar_aplicado")
    delta_score: str = Field(..., description="Texto do delta matemático (ex: '≥ 0.85' ou '< 0.85')")
    delta_score_cor: str = Field(default="normal", description="'normal' (verde) ou 'inverse' (vermelho)")
    revisao_humana_status: str = Field(..., description="'Dispensada' ou 'Exigida'")
    revisao_humana_motivo: str = Field(..., description="Motivo sintetizado do status de auditoria")
    revisao_humana_cor: str = Field(default="normal", description="'normal' (verde) ou 'inverse' (vermelho)")
    requer_atencao_mista: bool = Field(default=False, description="True quando atingiu o limiar mas exige revisão clínica")
    aviso_misto: Optional[str] = Field(None, description="Texto explicativo para retenção clínica com score suficiente")


def calcular_indicadores_qualidade_e_roteamento(
    *,
    qualidade_wf: Any,
    decisao_wf: Any,
) -> IndicadoresQualidadeRoteamento:
    """
    Segrega o atingimento do limiar matemático (score_combinado >= limiar_aplicado)
    da decisão de revisão humana (RN-08: urgência isolada NÃO exige revisão humana).
    """
    limiar_real = float(getattr(qualidade_wf, "limiar_aplicado", 0.85))
    score_comb = float(getattr(qualidade_wf, "score_combinado", 0.0))
    score_class = float(getattr(qualidade_wf, "score_classificacao", score_comb))
    score_ext = float(getattr(qualidade_wf, "score_extracao", score_comb))

    atingiu_limiar = bool(score_comb >= limiar_real)
    delta_score = f"≥ {limiar_real:.2f}" if atingiu_limiar else f"< {limiar_real:.2f}"
    delta_score_cor = "normal" if atingiu_limiar else "inverse"

    requer_auditoria = bool(getattr(decisao_wf, "requer_auditoria_humana", False))

    if requer_auditoria:
        revisao_status = "Exigida"
        revisao_cor = "inverse"
        if atingiu_limiar:
            revisao_motivo = "Por Regra Clínica"
            requer_mista = True
            aviso_misto = (
                f"ℹ️ **Limiar matemático atingido ({score_comb:.2f} ≥ {limiar_real:.2f})**, porém o "
                f"roteamento determinístico encaminhou o documento para **Revisão Humana** devido a critérios "
                f"clínicos de incerteza ou inconsistência (ex: conflito clínico impeditivo, campo ou sinal incerto, "
                f"urgência/prioridade indeterminada ou tipo documental fora da taxonomia)."
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


def eh_decisao_urgente(
    *,
    classificacao: Any,
    dados_extraidos: Any,
    decisao_wf: Any,
) -> bool:
    """
    Identifica urgência clínica preservando tanto a prioridade documental quanto o
    indicador clínico extraído (dados_extraidos.urgencia == SIM) e o destino canônico.
    """
    destinos_raw = [
        getattr(d, "value", str(d))
        for d in (getattr(decisao_wf, "destinos", None) or [])
    ]
    if Destino.FILA_URGENCIA_MEDICA.value in destinos_raw:
        return True
    if bool(getattr(decisao_wf, "alerta_simulado", False)):
        return True

    prio = getattr(classificacao, "nivel_prioridade", None)
    prio_val = getattr(prio, "value", str(prio or "")).upper()
    if prio_val == NivelPrioridade.URGENTE.value:
        return True

    urg = getattr(dados_extraidos, "urgencia", None)
    urg_val = getattr(urg, "value", str(urg or "")).upper()
    return urg_val == Urgencia.SIM.value


def montar_triagem_canonica(
    *,
    documento_id: str,
    classificacao: Classificacao,
    dados_extraidos: DadosExtraidos,
    qualidade_wf: Any,
    decisao_wf: Any,
    urgencia_efetiva: Optional[str] = None,
    res_oci: Optional[Dict[str, Any]] = None,
    caminho_alvo: Optional[str] = None,
    modo_simulacao_padrao: bool = False,
    canal_origem: str = "Bancada_Streamlit",
) -> TriagemMediFlow:
    """
    Constrói TriagemMediFlow preservando todos os campos extraídos (urgencia, exames,
    exames_laboratoriais, medicamentos, especialidade, NivelPrioridade.NAO_IDENTIFICADA)
    e aplicando ERRO_PERSISTENCIA com mensagem segura caso a persistência OCI falhe.
    """
    classif_final = Classificacao(
        tipo_documento=classificacao.tipo_documento,
        especialidade=list(classificacao.especialidade or []),
        nivel_prioridade=classificacao.nivel_prioridade,
        score_classificacao=float(getattr(qualidade_wf, "score_classificacao", classificacao.score_classificacao)),
    )

    kwargs_dados: Dict[str, Any] = {
        "paciente": dados_extraidos.paciente,
        "medico": dados_extraidos.medico,
        "diagnostico": dados_extraidos.diagnostico,
        "cid": dados_extraidos.cid,
        "exames": list(dados_extraidos.exames or []),
        "exames_laboratoriais": list(dados_extraidos.exames_laboratoriais or []),
        "medicamentos": list(dados_extraidos.medicamentos or []),
        "score_confianca_extracao": float(
            getattr(qualidade_wf, "score_extracao", dados_extraidos.score_confianca_extracao)
        ),
        "achados_criticos": dados_extraidos.achados_criticos,
        "inconsistencias_detectadas": list(dados_extraidos.inconsistencias_detectadas or []),
    }
    if urgencia_efetiva is not None:
        kwargs_dados["urgencia"] = Urgencia(str(urgencia_efetiva).upper())
    elif "urgencia" in dados_extraidos.model_fields_set:
        urg_raw = getattr(dados_extraidos.urgencia, "value", str(dados_extraidos.urgencia))
        kwargs_dados["urgencia"] = Urgencia(str(urg_raw).upper())

    dados_final = DadosExtraidos(**kwargs_dados)

    conflitos_finais: List[Conflito] = []
    for c in getattr(qualidade_wf, "conflitos", None) or []:
        if isinstance(c, Conflito):
            conflitos_finais.append(c)
        else:
            conflitos_finais.append(
                Conflito(
                    tipo=getattr(c, "tipo", str(c)),
                    gravidade=Gravidade(str(getattr(c, "gravidade", "ALTA")).upper()),
                    descricao=getattr(c, "descricao", ""),
                    campos=list(getattr(c, "campos", []) or []),
                )
            )

    qualidade_final = Qualidade(
        score_extracao=float(qualidade_wf.score_extracao),
        score_combinado=float(qualidade_wf.score_combinado),
        limiar_aplicado=float(qualidade_wf.limiar_aplicado),
        campos_ausentes=list(qualidade_wf.campos_ausentes or []),
        campos_incertos=list(qualidade_wf.campos_incertos or []),
        conflitos=conflitos_finais,
    )

    destinos_finais = [
        Destino(getattr(d, "value", d))
        for d in (getattr(decisao_wf, "destinos", None) or [Destino.FILA_REVISAO_HUMANA])
    ]
    requer_auditoria = bool(getattr(decisao_wf, "requer_auditoria_humana", False))
    justificativa = str(getattr(decisao_wf, "justificativa", "") or "")

    notificacao_obj = None
    if bool(getattr(decisao_wf, "alerta_simulado", False)):
        notificacao_obj = Notificacao(
            gerada=True,
            canal="SIMULADO_SLACK_PLANTAO",
            mensagem=f"ALERTA URGENTE [{documento_id}]: {justificativa}",
            status="REGISTRADA",
        )

    decisao_final = DecisaoRoteamento(
        destino_principal=destinos_finais[0],
        destinos=destinos_finais,
        requer_auditoria_humana=requer_auditoria,
        justificativa_roteamento=justificativa,
        notificacao=notificacao_obj,
    )

    status_clinico = StatusTriagem.EM_REVISAO if requer_auditoria else StatusTriagem.PROCESSADO
    bucket_padrao = os.getenv("OCI_BUCKET_NAME", "mediflow-documentos")

    if res_oci is None:
        return TriagemMediFlow(
            status=status_clinico,
            documento_id=documento_id,
            canal_origem=canal_origem,
            classificacao=classif_final,
            dados_extraidos=dados_final,
            qualidade=qualidade_final,
            decisao_roteamento=decisao_final,
            armazenamento_oci=ArmazenamentoOCI(
                bucket=bucket_padrao,
                caminho_objeto=caminho_alvo,
                status_backup="sucesso",
                modo_simulacao=modo_simulacao_padrao,
            ),
            erro=None,
        )

    if res_oci.get("status_backup") == "falha":
        return TriagemMediFlow(
            status=StatusTriagem.ERRO_PERSISTENCIA,
            documento_id=documento_id,
            canal_origem=canal_origem,
            classificacao=classif_final,
            dados_extraidos=dados_final,
            qualidade=qualidade_final,
            decisao_roteamento=decisao_final,
            armazenamento_oci=ArmazenamentoOCI(
                bucket=res_oci.get("bucket", bucket_padrao),
                caminho_objeto=res_oci.get("caminho_objeto"),
                status_backup="falha",
                modo_simulacao=bool(res_oci.get("modo_simulacao", False)),
            ),
            erro=ErroProcessamento(
                codigo=CodigoErro.ERRO_PERSISTENCIA,
                mensagem=res_oci.get("erro") or MENSAGEM_PUBLICA_FALHA_OCI,
            ),
        )

    return TriagemMediFlow(
        status=status_clinico,
        documento_id=documento_id,
        canal_origem=canal_origem,
        classificacao=classif_final,
        dados_extraidos=dados_final,
        qualidade=qualidade_final,
        decisao_roteamento=decisao_final,
        armazenamento_oci=ArmazenamentoOCI(
            bucket=res_oci.get("bucket", bucket_padrao),
            caminho_objeto=res_oci.get("caminho_objeto") or caminho_alvo,
            status_backup=res_oci.get("status_backup", "sucesso"),
            modo_simulacao=bool(res_oci.get("modo_simulacao", False)),
        ),
        erro=None,
    )
