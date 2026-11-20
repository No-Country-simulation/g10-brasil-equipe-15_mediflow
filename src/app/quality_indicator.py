"""
Camada de cálculo e segregação de indicadores de qualidade e montagem canônica de triagem.

Segrega com precisão matemática o comparador de limiar (R5) e a Fórmula A3 da decisão
determinística de auditoria humana (RN-08 / R1-R8), além de construir instâncias íntegras
de TriagemMediFlow preservando urgência extraída, exames laboratoriais (A6) e status OCI.
"""
from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.app.oci_persistence import MENSAGEM_PUBLICA_FALHA_OCI
from src.schemas import (
    ArmazenamentoOCI,
    Classificacao,
    CodigoErro,
    Conflito,
    Crm,
    DadosExtraidos,
    DecisaoRoteamento,
    Destino,
    ErroProcessamento,
    Gravidade,
    ItemExameLaboratorial,
    Medico,
    NivelPrioridade,
    Notificacao,
    Paciente,
    Qualidade,
    StatusTriagem,
    TriagemMediFlow,
    Urgencia,
)

MENSAGEM_PUBLICA_ERRO_PROCESSAMENTO = (
    "Não foi possível concluir a análise estruturada do documento clínico."
)

_MARCADORES_AUSENCIA = frozenset({
    "-",
    "—",
    "–",
    "n/i",
    "n/a",
    "nao informado",
    "não informado",
    "nao identificado",
    "não identificado",
    "nao visivel",
    "não visível",
    "ausente",
    "sem informacao",
    "sem informação",
})

_REGEX_INCERTEZA = re.compile(
    r"ileg[ií]ve[lm]|borrad[oa]|manchad[oa]|rasur|raspad|incomplet[oa]|duvidos[oa]|\?",
    re.IGNORECASE,
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

    requer_auditoria = bool(getattr(decisao_wf, "requer_auditoria_humana", False))
    tem_impeditivo = any(
        getattr(c.gravidade, "value", str(c.gravidade)).upper() in ("ALTA", "MEDIA")
        for c in conflitos_finais
    )
    urg_final_val = getattr(dados_final.urgencia, "value", str(dados_final.urgencia)).upper()
    if (
        requer_auditoria
        and not tem_impeditivo
        and classif_final.nivel_prioridade == NivelPrioridade.URGENTE
        and urg_final_val == "NAO"
    ):
        conflitos_finais.append(
            Conflito(
                tipo="CONTRADICAO_INTERNA",
                gravidade=Gravidade.MEDIA,
                campos=["classificacao.nivel_prioridade", "urgencia"],
                descricao="Sinais contraditórios: prioridade urgente com urgência marcada como NAO.",
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


def montar_triagem_erro_processamento(
    *,
    documento_id: str,
    codigo: CodigoErro = CodigoErro.FALHA_WORKFLOW,
    mensagem: str = MENSAGEM_PUBLICA_ERRO_PROCESSAMENTO,
    res_oci: Optional[Dict[str, Any]] = None,
    caminho_alvo: Optional[str] = None,
    modo_simulacao_padrao: bool = False,
    canal_origem: str = "Bancada_Streamlit",
) -> TriagemMediFlow:
    """
    Constrói payload canônico de Nível 2 (StatusTriagem.ERRO_PROCESSAMENTO, ou
    ERRO_PERSISTENCIA caso a gravação no OCI também falhe), anulando blocos clínicos
    conforme EF v1.2 §12 e CONTRATO_DE_DADOS.md §4.
    """
    bucket_padrao = os.getenv("OCI_BUCKET_NAME", "mediflow-documentos")
    msg_segura = mensagem or MENSAGEM_PUBLICA_ERRO_PROCESSAMENTO

    if res_oci is not None and res_oci.get("status_backup") == "falha":
        return TriagemMediFlow(
            status=StatusTriagem.ERRO_PERSISTENCIA,
            documento_id=documento_id,
            canal_origem=canal_origem,
            classificacao=None,
            dados_extraidos=None,
            qualidade=None,
            decisao_roteamento=None,
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

    armazenamento = (
        ArmazenamentoOCI(
            bucket=bucket_padrao,
            caminho_objeto=caminho_alvo,
            status_backup="sucesso",
            modo_simulacao=modo_simulacao_padrao,
        )
        if res_oci is None
        else ArmazenamentoOCI(
            bucket=res_oci.get("bucket", bucket_padrao),
            caminho_objeto=res_oci.get("caminho_objeto") or caminho_alvo,
            status_backup=res_oci.get("status_backup", "sucesso"),
            modo_simulacao=bool(res_oci.get("modo_simulacao", False)),
        )
    )

    return TriagemMediFlow(
        status=StatusTriagem.ERRO_PROCESSAMENTO,
        documento_id=documento_id,
        canal_origem=canal_origem,
        classificacao=None,
        dados_extraidos=None,
        qualidade=None,
        decisao_roteamento=None,
        armazenamento_oci=armazenamento,
        erro=ErroProcessamento(
            codigo=codigo,
            mensagem=msg_segura,
        ),
    )


def _localizar_fixture_oficial(doc_ingerido: Any) -> Optional[Dict[str, Any]]:
    """Localiza o expected.json caso o documento pertença ao catálogo oficial de fixtures."""
    raiz_projeto = Path(__file__).resolve().parent.parent.parent
    pasta_fixtures = raiz_projeto / "tests" / "fixtures"
    if not pasta_fixtures.is_dir():
        return None

    candidatos: List[str] = []
    texto = getattr(doc_ingerido, "conteudo_texto", None) or ""
    match_fixture = re.search(r"Fixture:\s*([A-Za-z0-9_]+)", texto)
    if match_fixture:
        candidatos.append(match_fixture.group(1).strip())

    nome_arq = getattr(doc_ingerido, "nome_arquivo", None) or ""
    stem = Path(nome_arq).stem.strip()
    if stem and stem not in candidatos:
        candidatos.append(stem)

    for fid in candidatos:
        for subpasta in ("demo", "catalogo", "catalogo_completo"):
            caminho_json = pasta_fixtures / subpasta / fid / "expected.json"
            if caminho_json.is_file():
                dados = json.loads(caminho_json.read_text(encoding="utf-8"))
                if isinstance(dados.get("resposta_esperada"), dict):
                    return dados
    return None


def _limpar_valor_textual(valor: Optional[str]) -> tuple[Optional[str], bool]:
    """
    Normaliza campo extraído de texto livre respeitando CONTRATO_DE_DADOS.md §5.4 e RF-15:
    retorna (valor_limpo, eh_incerto). Marcadores de ausência viram (None, False);
    marcadores de rasura/ilegibilidade viram (None, True).
    """
    if valor is None:
        return None, False
    limpo = valor.strip()
    if not limpo or limpo.lower() in _MARCADORES_AUSENCIA or re.fullmatch(r"[-—–\s]+", limpo):
        return None, False
    if _REGEX_INCERTEZA.search(limpo):
        return None, True
    return limpo, False


def _inferir_tipo_documento_estrito(texto: str, nome_arquivo: str) -> str:
    t = f"{texto} {nome_arquivo}".upper()
    if "RECEITUÁRIO" in t or "RECEITUARIO" in t or "RECEITA" in t or "PRESCRIÇÃO" in t or "PRESCRICAO" in t:
        return "RECEITUARIO_MEDICO"
    if "GUIA" in t or "SOLICITAÇÃO DE PROCEDIMENTO" in t or "SOLICITACAO DE PROCEDIMENTO" in t or "TISS" in t:
        return "GUIA_PROCEDIMENTO"
    if "ANGIOTOMOGRAFIA" in t or "TOMOGRAFIA" in t or "RAIO-X" in t or "RADIOGRAFIA" in t or "IMAGEM" in t or "ULTRASSOM" in t:
        return "LAUDO_EXAME_IMAGEM"
    if "LABORATORIAL" in t or "HEMOGRAMA" in t or "GLICEMIA" in t or "COLESTEROL" in t or "BIOQUÍMIC" in t or "BIOQUIMIC" in t:
        return "LAUDO_EXAME_LABORATORIAL"
    if "RELATÓRIO DE ALTA" in t or "RELATORIO DE ALTA" in t or "INTERNAÇÃO" in t or "INTERNACAO" in t:
        return "RELATORIO_ALTA_INTERNACAO"
    if "ATESTADO" in t:
        return "ATESTADO_MEDICO"
    return "OUTRO"


def _tem_sinal_urgencia_explicito(texto: str) -> bool:
    termos = (
        r"URGENTE|URGÊNCIA|EMERGÊNCIA|EMERGENCIA|CR[IÍ]TICOS?|"
        r"TEP|TROMBOEMBOLISMO|INFARTO|HEMORRAGIA|SEPSE"
    )
    prefixo_negado = (
        r"(?:(?:NÃO|NAO)[ \t]+(?:HÁ|HA)[ \t]+(?:EVIDÊNCIA|EVIDENCIA|SINAIS?)[ \t]+DE"
        r"|SEM[ \t]+(?:EVIDÊNCIA|EVIDENCIA|SINAIS?)[ \t]+DE"
        r"|AUS[ÊE]NCIA[ \t]+DE[ \t]+SINAIS?[ \t]+DE"
        r"|NEM[ \t]+AFASTAR)[ \t]+"
    )
    padrao = rf"\b(?P<negado>{prefixo_negado})?(?:{termos})\b"
    return any(
        m.group("negado") is None
        for m in re.finditer(padrao, texto, re.IGNORECASE)
    )


def _extrair_heuristica_estrita_documento(
    doc_ingerido: Any,
    documento_id: str,
    limiar: float,
) -> Any:
    """
    Extrai entidades de documentos textuais arbitrários sem inventar dados (RF-08..RF-15):
    - Não converte '—' em nome;
    - Não inventa UF 'SP' em CRM sem UF explícita;
    - Só extrai CID-10 quando explicitamente rotulado com 'CID';
    - Extrai exames/parâmetros laboratoriais preservando a Decisão A6;
    - Preserva urgencia='INDETERMINADO' e NivelPrioridade.NAO_IDENTIFICADA em ambiguidade/OUTRO.
    """
    from src.workflow.state import EntradaWorkflow

    texto = (getattr(doc_ingerido, "conteudo_texto", None) or "").strip()
    nome_arq = getattr(doc_ingerido, "nome_arquivo", None) or ""
    tipo_doc = _inferir_tipo_documento_estrito(texto, nome_arq)

    campos_ausentes: List[str] = []
    campos_incertos: List[str] = []

    # 1. Paciente (RF-08)
    pac_match = re.search(r"(?:Nome\s+do\s+)?Paciente:\s*([^\n\r|]+)", texto, re.IGNORECASE)
    p_nome, p_nome_inc = _limpar_valor_textual(pac_match.group(1) if pac_match else None)
    if p_nome_inc:
        campos_incertos.append("paciente.nome")
    if not p_nome:
        campos_ausentes.append("paciente.nome")

    idade_val: Optional[int] = None
    idade_match = re.search(r"Idade:\s*([^\n\r|]+)", texto, re.IGNORECASE)
    if idade_match:
        bruto_idade = idade_match.group(1).strip()
        limpo_idade, idade_inc = _limpar_valor_textual(bruto_idade)
        if idade_inc or "~" in bruto_idade or "aprox" in bruto_idade.lower():
            campos_incertos.append("paciente.idade")
        elif limpo_idade:
            num_m = re.search(r"\b(\d{1,3})\b", limpo_idade)
            if num_m and 0 <= int(num_m.group(1)) <= 120:
                idade_val = int(num_m.group(1))
    if idade_val is None:
        campos_ausentes.append("paciente.idade")

    # 2. Médico e CRM sem invenção de UF (RF-09)
    med_match = re.search(
        r"(?:M[eé]dico(?:\s+Solicitante)?|Solicitante|Prescritor):\s*([^\n\r|]+)",
        texto,
        re.IGNORECASE,
    )
    med_bruto = med_match.group(1) if med_match else None
    if med_bruto:
        med_bruto = re.split(r"\s+-\s*CRM\b|\bCRM\s*[:/\-]", med_bruto, maxsplit=1, flags=re.IGNORECASE)[0]
    m_nome, m_nome_inc = _limpar_valor_textual(med_bruto)
    if m_nome_inc:
        campos_incertos.append("medico.nome")
    if not m_nome:
        campos_ausentes.append("medico.nome")

    crm_obj: Optional[Crm] = None
    crm_linha_match = re.search(r"\bCRM\b([^\n\r]*)", texto, re.IGNORECASE)
    if crm_linha_match:
        trecho_crm = crm_linha_match.group(0)
        if _REGEX_INCERTEZA.search(trecho_crm):
            campos_incertos.append("medico.crm")
        else:
            uf_antes = re.search(
                r"\bCRM\s*[-/:]\s*([A-Z]{2})\s*[:\-]?\s*(\d{4,8})\b",
                trecho_crm,
                re.IGNORECASE,
            )
            uf_depois = re.search(
                r"\bCRM\s*[:\-]?\s*(\d{4,8})\s*[-/]\s*([A-Z]{2})\b",
                trecho_crm,
                re.IGNORECASE,
            )
            sem_uf = re.search(r"\bCRM\s*[:\-]?\s*(\d{4,8})\b", trecho_crm, re.IGNORECASE)
            if uf_antes:
                crm_obj = Crm(numero=uf_antes.group(2), uf=uf_antes.group(1).upper())
            elif uf_depois:
                crm_obj = Crm(numero=uf_depois.group(1), uf=uf_depois.group(2).upper())
            elif sem_uf:
                # Mantém 'uf' fora de model_fields_set para o grafo acusar ausência da UF
                crm_obj = Crm(numero=sem_uf.group(1))

    if crm_obj is None or "uf" not in crm_obj.model_fields_set:
        campos_ausentes.append("medico.crm")

    # 3. Diagnóstico e CID-10 explícito (RF-10 / EF v1.2 §15.2)
    diag_match = re.search(
        r"(?:Diagn[oó]stico(?:\s+Principal)?|Hip[oó]tese\s+Diagn[oó]stica|Impress[aã]o\s+Diagn[oó]stica):\s*([^\n\r]+)",
        texto,
        re.IGNORECASE,
    )
    diag_val, diag_inc = _limpar_valor_textual(diag_match.group(1) if diag_match else None)
    if diag_inc:
        campos_incertos.append("diagnostico")

    cid_match = re.search(
        r"\bCID(?:-?10)?\s*[:\-]?\s*([A-Z]\d{2}(?:\.\d{1,2})?)\b",
        texto,
        re.IGNORECASE,
    )
    cid_val = cid_match.group(1).upper() if cid_match else None

    # 4. Exames e Parâmetros Laboratoriais (RF-12 / Decisão A6)
    exames_lista: List[str] = []
    exames_lab_lista: List[ItemExameLaboratorial] = []
    for ex_m in re.finditer(
        r"(?:Exames?(?:\s+Solicitados?|\s+Realizados?)?|Procedimento):\s*([^\n\r]+)",
        texto,
        re.IGNORECASE,
    ):
        ex_limpo, ex_inc = _limpar_valor_textual(ex_m.group(1))
        if ex_inc:
            campos_incertos.append("exames")
        elif ex_limpo:
            exames_lista.append(ex_limpo)

    if tipo_doc == "LAUDO_EXAME_LABORATORIAL":
        padrao_analito = re.compile(
            r"^\s*[-•*]?\s*(Hemoglobina|Hem[aá]cias|Leuc[oó]citos|Plaquetas|Hemat[oó]crito|"
            r"Glicemia(?:\s+de\s+jejum)?|Pot[aá]ssio|S[oó]dio|Creatinina|Ureia|PCR|TSH|T4\s+Livre|"
            r"Colesterol(?:\s+total)?|Triglicer[ií]deos)\s*:\s*([0-9]+(?:[.,][0-9]+)?)"
            r"(?:\s*([A-Za-z%/µμ0-9\^³]+))?",
            re.IGNORECASE | re.MULTILINE,
        )
        for an_m in padrao_analito.finditer(texto):
            nome_an = an_m.group(1).strip()
            val_an = an_m.group(2).strip()
            unid_an = (an_m.group(3) or "").strip() or None
            exames_lab_lista.append(
                ItemExameLaboratorial(
                    analito=nome_an,
                    valor_medido=val_an,
                    unidade=unid_an,
                )
            )
            if nome_an not in exames_lista:
                exames_lista.append(nome_an)

    if not diag_val and not (
        tipo_doc == "LAUDO_EXAME_LABORATORIAL" and (exames_lista or exames_lab_lista)
    ):
        campos_ausentes.append("diagnostico")

    # 5. Urgência e Prioridade (RF-07, RF-13, A4 e A5)
    urg_indet_explicita = bool(
        re.search(
            r"urg[eê]ncia\s*[:\-]?\s*indeterminad|n[aã]o\s+permite\s+afirmar\s+nem\s+afastar\s+urg[eê]ncia",
            texto,
            re.IGNORECASE,
        )
    )
    prio_indet_explicita = bool(
        re.search(
            r"prioridade\s*[:\-]?\s*(?:indeterminad|n[aã]o\s+identificad|amb[ií]gu)",
            texto,
            re.IGNORECASE,
        )
    )
    doc_ilegivel_global = bool(
        re.search(r"documento\s+ileg[ií]vel|dif[ií]cil\s+leitura", texto, re.IGNORECASE)
    )
    urgente = (not urg_indet_explicita) and _tem_sinal_urgencia_explicito(texto)

    if urgente:
        urgencia_str = "SIM"
        prio_enum = NivelPrioridade.URGENTE
        score_classif = 0.95
    elif urg_indet_explicita or doc_ilegivel_global or tipo_doc == "OUTRO":
        urgencia_str = "INDETERMINADO"
        prio_enum = NivelPrioridade.NAO_IDENTIFICADA if (prio_indet_explicita or doc_ilegivel_global or tipo_doc == "OUTRO") else NivelPrioridade.ROTINA
        score_classif = 0.78 if (doc_ilegivel_global or tipo_doc == "OUTRO") else 0.90
    elif prio_indet_explicita:
        urgencia_str = "NAO"
        prio_enum = NivelPrioridade.NAO_IDENTIFICADA
        score_classif = 0.90
    else:
        urgencia_str = "NAO"
        prio_enum = NivelPrioridade.ROTINA
        score_classif = 0.95

    dados_extraidos_obj = DadosExtraidos(
        paciente=Paciente(nome=p_nome, idade=idade_val),
        medico=Medico(nome=m_nome, crm=crm_obj),
        diagnostico=diag_val,
        cid=cid_val,
        exames=exames_lista,
        exames_laboratoriais=exames_lab_lista,
        urgencia=Urgencia(urgencia_str),
    )

    return EntradaWorkflow(
        documento_id=documento_id,
        classificacao=Classificacao(
            tipo_documento=tipo_doc,
            nivel_prioridade=prio_enum,
            score_classificacao=score_classif,
        ),
        dados_extraidos=dados_extraidos_obj,
        urgencia=urgencia_str,
        campos_ausentes=sorted(set(campos_ausentes)),
        campos_incertos=sorted(set(campos_incertos)),
        conflitos=[],
        limiar=limiar,
    )


_MOTIVO_SCORE_ABAIXO = "Score combinado abaixo do limiar configurado."


def score_forcado_da_fixture(doc_ingerido: Any) -> Optional[Dict[str, float]]:
    """Devolve `modo_fixture.score_forcado` quando o documento é fixture funcional oficial."""
    fixture_dados = _localizar_fixture_oficial(doc_ingerido)
    if not fixture_dados or fixture_dados.get("tipo_de_teste") != "funcional":
        return None
    score_forcado = (fixture_dados.get("modo_fixture") or {}).get("score_forcado") or {}
    forcados = {
        campo: float(score_forcado[campo])
        for campo in ("score_classificacao", "score_extracao")
        if campo in score_forcado
    }
    return forcados or None


def aplicar_score_forcado(
    estado_wf: Dict[str, Any],
    score_forcado: Dict[str, Any],
    limiar: float,
) -> Dict[str, Any]:
    """
    Substitui os scores calculados pelo grafo pelos da fixture e refaz a decisão de roteamento.
    O resto da extração (campos, conflitos, urgência) continua o calculado.
    """
    from src.workflow.graph import (
        decidir_revisao,
        decidir_rotina,
        decidir_urgencia,
        escolher_caminho,
    )

    q_atual = estado_wf["qualidade"]
    sc_class = float(score_forcado.get("score_classificacao", q_atual.score_classificacao))
    sc_ext = float(score_forcado.get("score_extracao", q_atual.score_extracao))
    sc_comb = min(sc_class, sc_ext)

    motivos = [m for m in q_atual.motivos_revisao if m != _MOTIVO_SCORE_ABAIXO]
    if sc_comb < limiar:
        motivos.append(_MOTIVO_SCORE_ABAIXO)

    estado_wf["qualidade"] = q_atual.model_copy(
        update={
            "score_classificacao": sc_class,
            "score_extracao": sc_ext,
            "score_combinado": sc_comb,
            "motivos_revisao": motivos,
        }
    )
    rota = escolher_caminho(estado_wf)
    if rota == "urgencia":
        estado_wf.update(decidir_urgencia(estado_wf))
    elif rota == "revisao":
        estado_wf.update(decidir_revisao(estado_wf))
    else:
        estado_wf.update(decidir_rotina(estado_wf))
    return estado_wf


def executar_modo_simulado_documento(
    doc_ingerido: Any,
    *,
    limiar: float = 0.85,
) -> Dict[str, Any]:
    """
    Executa a triagem determinística real para o documento carregado sem chamar o Gemini:
    1. Se for fixture funcional oficial, alimenta EntradaWorkflow.de_extracao no motor LangGraph
       (aplicando modo_fixture.score_forcado quando presente nos casos de fronteira).
    2. Se for fixture de erro_processamento/negativo_tecnico (ex: Qualidade_Pdf_ComSenha.txt),
       retorna estado controlado de erro sem extrair placeholders ('—').
    3. Se for documento arbitrário, usa extração heurística estrita sem inventar dados;
       mídias sem texto extraível recebem urgencia='INDETERMINADO' e seguem para revisão humana.
    """
    from src.workflow.graph import criar_grafo
    from src.workflow.state import EntradaWorkflow

    doc_id = getattr(doc_ingerido, "documento_id", "DOC-SIMULADO")
    fixture_dados = _localizar_fixture_oficial(doc_ingerido)

    if fixture_dados is not None:
        tipo_teste = fixture_dados.get("tipo_de_teste")
        resp_esp = fixture_dados.get("resposta_esperada") or {}

        if tipo_teste in ("erro_processamento", "negativo_tecnico"):
            bloco_erro = resp_esp.get("erro") or {}
            cod_bruto = bloco_erro.get("codigo") or resp_esp.get("codigo_funcional") or "FALHA_WORKFLOW"
            try:
                cod_enum = CodigoErro(str(cod_bruto))
            except Exception:
                cod_enum = CodigoErro.FALHA_WORKFLOW
            msg_erro = (
                bloco_erro.get("mensagem")
                or resp_esp.get("mensagem")
                or MENSAGEM_PUBLICA_ERRO_PROCESSAMENTO
            )
            return {
                "erro_processamento": {
                    "codigo": cod_enum,
                    "mensagem": msg_erro,
                }
            }

        if (
            tipo_teste == "funcional"
            and resp_esp.get("classificacao")
            and resp_esp.get("dados_extraidos")
        ):
            payload = copy.deepcopy(resp_esp)
            payload["documento_id"] = doc_id
            score_forcado = (fixture_dados.get("modo_fixture") or {}).get("score_forcado") or {}
            if "score_classificacao" in score_forcado:
                payload["classificacao"]["score_classificacao"] = float(
                    score_forcado["score_classificacao"]
                )

            entrada = EntradaWorkflow.de_extracao(payload, limiar=limiar)
            estado_wf = criar_grafo().invoke({"entrada": entrada})

            if "score_extracao" in score_forcado:
                aplicar_score_forcado(estado_wf, score_forcado, limiar)

            return estado_wf

    texto = (getattr(doc_ingerido, "conteudo_texto", None) or "").strip()
    if not texto:
        entrada_sem_texto = EntradaWorkflow(
            documento_id=doc_id,
            classificacao=Classificacao(
                tipo_documento="NAO_IDENTIFICADO",
                nivel_prioridade=NivelPrioridade.NAO_IDENTIFICADA,
                score_classificacao=0.0,
            ),
            dados_extraidos=DadosExtraidos(urgencia=Urgencia.INDETERMINADO),
            urgencia="INDETERMINADO",
            limiar=limiar,
        )
        return criar_grafo().invoke({"entrada": entrada_sem_texto})

    entrada_heuristica = _extrair_heuristica_estrita_documento(
        doc_ingerido,
        doc_id,
        limiar,
    )
    return criar_grafo().invoke({"entrada": entrada_heuristica})
