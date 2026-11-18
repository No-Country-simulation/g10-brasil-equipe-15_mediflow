"""
MediFlow — Bancada de Demonstração e Inspeção Clínica (Streamlit).
Equipe 15 · Hackathon ONE G10 (Oracle & Alura).
Permite ingestão multimodal (PDF, TXT, Imagens), classificação e extração via Gemini,
orquestração determinística via LangGraph, persistência segura no OCI Object Storage
e inspeção da Fila Lógica de Revisão Humana (HITL) conforme EF v1.2.
"""
import sys
from pathlib import Path

# Garante que a raiz do projeto esteja no sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import os
import re
from typing import Any, Dict, List, Optional

import streamlit as st
from dotenv import load_dotenv

from src.app.oci_persistence import (
    executar_persistencia_triagem,
    resolver_caminho_resultado_oci,
)
from src.app.quality_indicator import (
    calcular_indicadores_qualidade_e_roteamento,
    eh_decisao_urgente,
    executar_modo_simulado_documento,
    montar_triagem_canonica,
)
from src.app.triage_pipeline import processar_documento_com_agente
from src.ingestion import DocumentLoader, IngestaoError, resolver_mime_type
from src.schemas import (
    Classificacao,
    ClassificacaoClinica,
    Crm,
    DadosExtraidos,
    Destino,
    Medico,
    NivelPrioridade,
    Paciente,
    StatusTriagem,
    Urgencia,
)
from src.schemas.clinical import CAMPOS_OBRIGATORIOS, GRAVIDADES_IMPEDITIVAS
from src.services.gemini_service import GeminiService
from src.workflow.graph import criar_grafo
from src.workflow.state import EntradaWorkflow

load_dotenv(override=True)

MAPA_DESTINOS_ROTULOS = {
    "FILA_URGENCIA_MEDICA": "Fila de Urgência Médica (Plantão / Emergência)",
    "EMERGENCIA": "Fila de Urgência Médica (Plantão / Emergência)",
    "EMERGENCIA_HOSPITALAR": "Fila de Urgência Médica (Plantão / Emergência)",
    "FILA_REVISAO_HUMANA": "Fila de Revisão Humana (Auditoria Clínica)",
    "REVISAO_HUMANA": "Fila de Revisão Humana (Auditoria Clínica)",
    "PRONTUARIO_ELETRONICO": "Prontuário Eletrônico do Paciente",
    "FARMACIA_HOSPITALAR": "Farmácia Hospitalar",
    "AUDITORIA_AUTORIZACOES": "Auditoria de Autorizações / Guias",
}


def _resolver_prioridade(prioridade_str: str) -> NivelPrioridade:
    prio_upper = str(prioridade_str or "").strip().upper()
    if "URGENTE" in prio_upper or "EMERGENCIA" in prio_upper:
        return NivelPrioridade.URGENTE
    if (
        "NAO_IDENTIFICADA" in prio_upper
        or "NÃO IDENTIFICADA" in prio_upper
        or "AMBIGU" in prio_upper
        or prio_upper in ("", "N/A")
    ):
        return NivelPrioridade.NAO_IDENTIFICADA
    return NivelPrioridade.ROTINA


def executar_fluxo_agente(
    documento_id: str,
    tipo_documento: str,
    prioridade_str: str,
    score_classificacao: float,
    paciente_dict: Dict[str, Any],
    medico_dict: Dict[str, Any],
    diagnostico: Optional[str],
    cid: Optional[str] = None,
    medicamentos: Optional[List[Any]] = None,
    exames: Optional[List[Any]] = None,
    urgencia: Optional[str] = None,
    especialidade: Optional[List[str] | str] = None,
    limiar: float = 0.85,
) -> Dict[str, Any]:
    """Invoca deterministicamente o motor LangGraph para decisão clínica e roteamento."""
    prio_enum = _resolver_prioridade(prioridade_str)
    urg_norm = (
        str(urgencia).strip().upper()
        if urgencia is not None
        else ("SIM" if prio_enum == NivelPrioridade.URGENTE else "NAO")
    )
    if urg_norm not in ("SIM", "NAO", "INDETERMINADO"):
        urg_norm = "INDETERMINADO"

    # 1. Detecção rigorosa de campos ausentes / ilegíveis nos cenários simulados
    campos_ausentes: List[str] = []
    campos_incertos: List[str] = []

    p_nome = paciente_dict.get("nome")
    if not p_nome or str(p_nome).strip() in ("N/I", "") or "não identificado" in str(p_nome).lower():
        campos_ausentes.append("paciente.nome")
        p_nome_clean = None
    elif "ilegível" in str(p_nome).lower():
        campos_ausentes.append("paciente.nome")
        campos_incertos.append("paciente.nome")
        p_nome_clean = None
    else:
        p_nome_clean = str(p_nome)

    p_idade = paciente_dict.get("idade")
    if p_idade is None:
        campos_ausentes.append("paciente.idade")

    m_nome = medico_dict.get("nome")
    if not m_nome or str(m_nome).strip() in ("N/I", "") or "não identificado" in str(m_nome).lower():
        campos_ausentes.append("medico.nome")
        m_nome_clean = None
    elif "ilegível" in str(m_nome).lower():
        campos_ausentes.append("medico.nome")
        campos_incertos.append("medico.nome")
        m_nome_clean = None
    else:
        m_nome_clean = str(m_nome)

    crm_val = medico_dict.get("crm")
    crm_obj = None
    if not crm_val or str(crm_val).strip() in ("N/I", ""):
        campos_ausentes.append("medico.crm")
    elif "?" in str(crm_val) or "ilegível" in str(crm_val).lower():
        campos_ausentes.append("medico.crm")
        campos_incertos.append("medico.crm")
    else:
        crm_limpo = re.sub(r"(?i)^crm[\s\:\/\.\-]*", "", str(crm_val)).strip()
        partes = re.split(r"[-/]", crm_limpo)
        if len(partes) == 2 and partes[0].strip().isdigit():
            crm_obj = Crm(numero=partes[0].strip(), uf=partes[1].strip().upper())
        elif partes[0].strip().isdigit():
            crm_obj = Crm(numero=partes[0].strip(), uf="SP")
        else:
            campos_ausentes.append("medico.crm")

    diag_clean = diagnostico
    if not diagnostico or str(diagnostico).strip() in ("N/I", ""):
        if "LABORATORIAL" not in str(tipo_documento).upper() or not exames:
            campos_ausentes.append("diagnostico")
        diag_clean = None
    elif "borrada" in str(diagnostico).lower() or "ilegível" in str(diagnostico).lower():
        campos_ausentes.append("diagnostico")
        campos_incertos.append("diagnostico")
        diag_clean = None

    paciente_obj = Paciente(nome=p_nome_clean, idade=p_idade)
    medico_obj = Medico(nome=m_nome_clean, crm=crm_obj)
    dados_extraidos = DadosExtraidos(
        paciente=paciente_obj,
        medico=medico_obj,
        diagnostico=diag_clean,
        cid=cid,
        medicamentos=medicamentos or [],
        exames=exames or [],
        urgencia=Urgencia(urg_norm),
    )

    esp_lista = (
        [s.strip() for s in especialidade.split("/") if s.strip()]
        if isinstance(especialidade, str)
        else list(especialidade or [])
    )

    classificacao = ClassificacaoClinica(
        tipo_documento=tipo_documento,
        especialidade=esp_lista,
        nivel_prioridade=prio_enum,
        score_confianca_classificacao=score_classificacao,
    )

    entrada = EntradaWorkflow(
        documento_id=documento_id,
        classificacao=classificacao,
        dados_extraidos=dados_extraidos,
        urgencia=urg_norm,
        campos_ausentes=sorted(set(campos_ausentes)),
        campos_incertos=sorted(set(campos_incertos)),
        conflitos=[],
        limiar=limiar,
    )

    grafo = criar_grafo()
    return grafo.invoke({"entrada": entrada})


def _formatar_ausente(valor: Optional[str]) -> str:
    if not valor or not str(valor).strip():
        return "Não identificado no documento"
    return str(valor)


# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA (STREAMLIT NATIVO)
# ==============================================================================
st.set_page_config(
    page_title="MediFlow — Triagem Clínica Autônoma",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    .main-header {
        font-size: 2.1rem;
        font-weight: 700;
        margin-bottom: 2px;
    }
    .sub-header {
        font-size: 0.95rem;
        opacity: 0.8;
        margin-bottom: 18px;
    }
    /* Responsividade e prevenção de truncamento em janelas estreitas */
    [data-testid="stMetricValue"] {
        font-size: 1.45rem !important;
        white-space: nowrap;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.82rem !important;
    }
    button[kind="primary"], button[kind="secondary"] {
        white-space: normal !important;
        word-break: normal !important;
        line-height: 1.25 !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ==============================================================================
# CENÁRIOS DEMO OFICIAIS (DO EDITAL E FIXTURES CANÔNICOS — RN-08)
# ==============================================================================
CENARIOS_DEMO = {
    "Cenário 1: Rotina (RX de Tórax Normal)": {
        "arquivo": "01_laudo_rotina.pdf",
        "tipo": "LAUDO_EXAME_IMAGEM",
        "especialidade": "Radiologia",
        "prioridade": "ROTINA",
        "urgencia": "NAO",
        "score_classif": 0.96,
        "paciente": "João Carlos da Silva",
        "idade": 42,
        "medico": "Dr. Roberto Mendes",
        "crm": "112345-SP",
        "diagnostico": "Radiografia de tórax dentro dos limites da normalidade.",
        "cid": None,
        "exames": ["Radiografia de tórax PA e perfil"],
        "requer_auditoria": False,
    },
    "Cenário 2: Urgência Crítica Isolada (Angiotomografia - TEP Agudo)": {
        "arquivo": "02_laudo_urgencia_tep.pdf",
        "tipo": "LAUDO_EXAME_IMAGEM",
        "especialidade": "Radiologia / Pneumologia",
        "prioridade": "URGENTE",
        "urgencia": "SIM",
        "score_classif": 0.99,
        "paciente": "Maria Eduarda Santos",
        "idade": 61,
        "medico": "Dra. Camila Alencar",
        "crm": "98765-SP",
        "diagnostico": "Tromboembolismo Pulmonar Agudo Massivo",
        "cid": "I26.9",
        "exames": ["Angiotomografia computadorizada de artérias pulmonares"],
        "requer_auditoria": False,
    },
    "Cenário 3: Ambiguidade / Rasura (Receituário - Fila de Revisão Humana)": {
        "arquivo": "03_receituario_ambiguo.pdf",
        "tipo": "RECEITUARIO_MEDICO",
        "especialidade": "Clínica Médica",
        "prioridade": "NAO_IDENTIFICADA",
        "urgencia": "INDETERMINADO",
        "score_classif": 0.80,
        "paciente": "Maria de Fátima Oliveira [Nome parcialmente ilegível]",
        "idade": 55,
        "medico": "Dr. [Assinatura ilegível]",
        "crm": "123...?-SP",
        "diagnostico": "Prescrição de anti-hipertensivo com dosagem borrada",
        "cid": None,
        "exames": [],
        "requer_auditoria": True,
    },
}

# ==============================================================================
# INICIALIZAÇÃO DE ESTADO DE SESSÃO
# ==============================================================================
if "doc_id_atual" not in st.session_state:
    st.session_state.doc_id_atual = None

if "resultado_ia" not in st.session_state:
    st.session_state.resultado_ia = None

if "cache_persistencia_oci" not in st.session_state:
    st.session_state.cache_persistencia_oci = {}

# ==============================================================================
# BARRA LATERAL (CONTROLES E INGESTÃO)
# ==============================================================================
with st.sidebar:
    st.markdown("### 🏥 MediFlow `v2.0`")
    st.caption("Agente Autônomo para Triagem Clínica · Equipe 15")

    st.markdown("---")

    modo_entrada = st.segmented_control(
        "Origem do Documento:",
        options=["Cenários Oficiais (Demo)", "Upload de Arquivo Real"],
        default="Cenários Oficiais (Demo)",
    )

    doc_ingerido = None
    dados_mock = None

    if modo_entrada == "Cenários Oficiais (Demo)":
        cenario_escolhido = st.selectbox(
            "Selecione um caso clínico do edital:",
            list(CENARIOS_DEMO.keys()),
        )
        dados_mock = CENARIOS_DEMO[cenario_escolhido]
        caminho_pdf = ROOT_DIR / "data" / "samples" / dados_mock["arquivo"]

        if caminho_pdf.exists():
            doc_ingerido = DocumentLoader.carregar_arquivo(caminho_pdf)
        else:
            st.warning("Arquivo PDF de demonstração não encontrado localmente.", title="Arquivo ausente")

    else:
        uploaded_file = st.file_uploader(
            "Arraste ou selecione um laudo/receita:",
            type=["pdf", "png", "jpg", "webp", "txt"],
            help="Formatos aceitos: PDF, TXT ou Imagens (Máx: 10MB / 20 páginas)",
        )

        if uploaded_file is not None:
            try:
                bytes_data = uploaded_file.read()
                doc_ingerido = DocumentLoader.carregar_bytes(
                    conteudo_bytes=bytes_data,
                    nome_arquivo=uploaded_file.name,
                )
                st.success(
                    f"Arquivo validado com sucesso! ({doc_ingerido.tamanho_bytes / 1024:.1f} KB)",
                    title="Upload Concluído",
                )
            except IngestaoError as e:
                st.error(f"Rejeição na borda ({e.codigo}): {e.mensagem}", title="Arquivo Inválido")
            except Exception:
                st.error(
                    "Não foi possível processar o arquivo enviado. Verifique o formato e tente novamente.",
                    title="Falha na Leitura",
                )

    st.markdown("---")
    chave_env = os.getenv("GEMINI_API_KEY", "")
    tem_chave_valida = bool(chave_env and not chave_env.startswith("sua_chave"))
    api_key_custom = st.text_input(
        "🔑 Chave Gemini API (Opcional):",
        value=chave_env if tem_chave_valida else "",
        type="password",
        help="Insira sua chave do Google AI Studio para inferência ao vivo com Gemini Multimodal.",
    )

    st.markdown("---")
    st.markdown("**Hackathon ONE G10 — Oracle & Alura**")
    st.caption("LangGraph · Pydantic v2 · OCI Object Storage Always Free.")

# ==============================================================================
# CABEÇALHO PRINCIPAL
# ==============================================================================
st.markdown("<div class='main-header'>MediFlow — Triagem Clínica Documental</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='sub-header'>Ingestão Blindada PyMuPDF · Contrato Pydantic v2 · Roteamento Determinístico LangGraph · OCI Object Storage</div>",
    unsafe_allow_html=True,
)

# ==============================================================================
# CORPO PRINCIPAL (VISÃO LADO A LADO)
# ==============================================================================
if doc_ingerido is not None:
    if st.session_state.doc_id_atual != doc_ingerido.documento_id:
        st.session_state.doc_id_atual = doc_ingerido.documento_id
        st.session_state.resultado_ia = None
        st.session_state.cache_persistencia_oci = {}

    col_esquerda, col_direita = st.columns([1, 1], gap="medium")

    # -------------------------------------------------------------------------
    # COLUNA ESQUERDA: DOCUMENTO ORIGINAL E METADADOS DA INGESTÃO
    # -------------------------------------------------------------------------
    with col_esquerda:
        st.subheader("📄 Documento Ingerido", anchor=False)

        tam_str = (
            f"{doc_ingerido.tamanho_bytes} B"
            if doc_ingerido.tamanho_bytes < 1024
            else f"{doc_ingerido.tamanho_bytes / 1024:.1f} KB"
        )
        with st.container(horizontal=True):
            st.metric("Formato", doc_ingerido.formato, border=True)
            st.metric("Páginas", doc_ingerido.total_paginas, border=True)
            st.metric("Tamanho", tam_str, border=True)
            st.metric("OCR", "Sim" if doc_ingerido.requer_ocr else "Não", border=True)

        st.caption(
            f"**Identificador Canônico:** `{doc_ingerido.documento_id}` | **Arquivo:** `{doc_ingerido.nome_arquivo}`"
        )

        if doc_ingerido.formato in ["JPG", "JPEG", "PNG", "WEBP"] and doc_ingerido.conteudo_bytes:
            st.markdown("**Visualização do Documento Digitalizado:**")
            st.image(doc_ingerido.conteudo_bytes, caption=doc_ingerido.nome_arquivo, width="stretch")
        else:
            st.markdown("**Texto Extraído pelo PyMuPDF:**")
            st.text_area(
                label="Conteúdo Bruto",
                value=(
                    doc_ingerido.conteudo_texto
                    if doc_ingerido.conteudo_texto
                    else "[Mídia em Imagem/Digitalizada — análise multimodal via Gemini]"
                ),
                height=360,
                disabled=True,
                label_visibility="collapsed",
            )

    # -------------------------------------------------------------------------
    # COLUNA DIREITA: RESULTADO DA TRIAGEM CLÍNICA & DECISÃO DO AGENTE
    # -------------------------------------------------------------------------
    with col_direita:
        st.subheader("⚖️ Decisão do Agente & Roteamento", anchor=False)

        limiar_configurado = float(os.getenv("LIMIAR_CONFIANCA", "0.85"))
        decisao_wf = None
        qualidade_wf = None
        classif_obj: Optional[Classificacao] = None
        dados_ext_obj: Optional[DadosExtraidos] = None
        urgencia_efetiva: Optional[str] = None
        forcar_simulado_oci = False

        if dados_mock:
            estado_wf = executar_fluxo_agente(
                documento_id=doc_ingerido.documento_id,
                tipo_documento=dados_mock["tipo"],
                prioridade_str=dados_mock["prioridade"],
                score_classificacao=dados_mock["score_classif"],
                paciente_dict={"nome": dados_mock["paciente"], "idade": dados_mock["idade"]},
                medico_dict={"nome": dados_mock["medico"], "crm": dados_mock["crm"]},
                diagnostico=dados_mock["diagnostico"],
                cid=dados_mock["cid"],
                exames=dados_mock.get("exames", []),
                urgencia=dados_mock["urgencia"],
                especialidade=dados_mock.get("especialidade"),
                limiar=limiar_configurado,
            )
            entrada_wf = estado_wf["entrada"]
            decisao_wf = estado_wf.get("decisao")
            qualidade_wf = estado_wf.get("qualidade")
            classif_obj = entrada_wf.classificacao
            dados_ext_obj = entrada_wf.dados_extraidos
            urgencia_efetiva = entrada_wf.urgencia
            forcar_simulado_oci = True
        else:
            st.info(
                "Arquivo validado na ingestão! Selecione o modo de execução abaixo.",
                title="Pronto para Análise",
            )

            with st.container(horizontal=True):
                executar_ia = st.button(
                    "Analisar com IA",
                    type="primary",
                    icon=":material/auto_awesome:",
                    help="Executa a extração multimodal via GeminiService e o grafo determinístico LangGraph.",
                )
                usar_fallback_teste = st.button(
                    "Modo Simulado",
                    icon=":material/science:",
                    help="Executa a triagem determinística local em modo simulado (sem chamadas externas).",
                )

            if executar_ia:
                with st.spinner("Analisando documento clínico com Gemini Multimodal e Motor LangGraph..."):
                    service = GeminiService(
                        api_key=api_key_custom or os.getenv("GEMINI_API_KEY"),
                        model_name=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
                    )
                    mime_tipo = resolver_mime_type(doc_ingerido)

                    resultado_pipeline = processar_documento_com_agente(
                        servico=service,
                        documento_id=doc_ingerido.documento_id,
                        conteudo_texto=doc_ingerido.conteudo_texto or "",
                        conteudo_bytes=doc_ingerido.conteudo_bytes,
                        mime_type=mime_tipo,
                        limiar=limiar_configurado,
                    )
                    estado_wf = resultado_pipeline["estado_workflow"]
                    entrada_wf = estado_wf["entrada"]
                    t_val = getattr(entrada_wf.classificacao, "tipo_documento", None)
                    tipo_str = getattr(t_val, "value", str(t_val or ""))
                    eh_fallback_llm = (
                        tipo_str == "NAO_IDENTIFICADO"
                        and float(entrada_wf.classificacao.score_confianca_classificacao) == 0.0
                    ) or (
                        float(estado_wf["qualidade"].score_extracao) == 0.0
                        and not entrada_wf.dados_extraidos.diagnostico
                        and not entrada_wf.dados_extraidos.paciente.nome
                    )

                    st.session_state.resultado_ia = {
                        "decisao_wf": estado_wf.get("decisao"),
                        "qualidade_wf": estado_wf.get("qualidade"),
                        "classif_obj": entrada_wf.classificacao,
                        "dados_ext_obj": entrada_wf.dados_extraidos,
                        "urgencia_efetiva": entrada_wf.urgencia,
                        "chave_ativa": bool(api_key_custom or tem_chave_valida),
                        "fallback_llm": eh_fallback_llm,
                        "simulado": False,
                    }
                    st.session_state.cache_persistencia_oci = {}

            if usar_fallback_teste:
                estado_wf = executar_modo_simulado_documento(
                    doc_ingerido,
                    limiar=limiar_configurado,
                )
                entrada_wf = estado_wf["entrada"]
                st.session_state.resultado_ia = {
                    "decisao_wf": estado_wf.get("decisao"),
                    "qualidade_wf": estado_wf.get("qualidade"),
                    "classif_obj": entrada_wf.classificacao,
                    "dados_ext_obj": entrada_wf.dados_extraidos,
                    "urgencia_efetiva": entrada_wf.urgencia,
                    "chave_ativa": True,
                    "fallback_llm": False,
                    "simulado": True,
                }
                st.session_state.cache_persistencia_oci = {}

            if st.session_state.resultado_ia:
                res = st.session_state.resultado_ia
                decisao_wf = res["decisao_wf"]
                qualidade_wf = res["qualidade_wf"]
                classif_obj = res["classif_obj"]
                dados_ext_obj = res["dados_ext_obj"]
                urgencia_efetiva = res["urgencia_efetiva"]
                forcar_simulado_oci = bool(res.get("simulado"))

                if not res.get("chave_ativa") and not res.get("simulado"):
                    st.warning(
                        "Chave GEMINI_API_KEY não configurada ou inválida. O adaptador acionou o fallback seguro (EF v1.2 §12), encaminhando para revisão humana.",
                        title="Fallback Resiliente Ativado",
                    )
                elif res.get("fallback_llm") and not res.get("simulado"):
                    st.warning(
                        "O provedor Gemini não respondeu no tempo limite ou retornou formato fora do schema. O fallback seguro (EF v1.2 §12 / RF-24) encaminhou o documento para revisão humana.",
                        title="Fallback Resiliente por Falha/Timeout do Modelo",
                    )

        # ---------------------------------------------------------------------
        # 2. PERSISTÊNCIA OCI E RENDERIZAÇÃO FIEL DA DECISÃO DO AGENTE
        # ---------------------------------------------------------------------
        if (
            decisao_wf is not None
            and qualidade_wf is not None
            and classif_obj is not None
            and dados_ext_obj is not None
        ):
            destinos_raw = [
                d.value if hasattr(d, "value") else str(d)
                for d in decisao_wf.destinos
            ]
            destinos_nomes = [MAPA_DESTINOS_ROTULOS.get(d, d) for d in destinos_raw]
            destinos_str = " + ".join(destinos_nomes)

            requer_auditoria = bool(decisao_wf.requer_auditoria_humana)
            eh_urgente = eh_decisao_urgente(
                classificacao=classif_obj,
                dados_extraidos=dados_ext_obj,
                decisao_wf=decisao_wf,
            )
            status_clinico = (
                StatusTriagem.EM_REVISAO if requer_auditoria else StatusTriagem.PROCESSADO
            )
            caminho_oci_alvo = resolver_caminho_resultado_oci(
                doc_ingerido.documento_id,
                status_clinico,
                eh_urgente,
            )

            triagem_candidata = montar_triagem_canonica(
                documento_id=doc_ingerido.documento_id,
                classificacao=classif_obj,
                dados_extraidos=dados_ext_obj,
                qualidade_wf=qualidade_wf,
                decisao_wf=decisao_wf,
                urgencia_efetiva=urgencia_efetiva,
                res_oci=None,
                caminho_alvo=caminho_oci_alvo,
                modo_simulacao_padrao=forcar_simulado_oci,
            )

            chave_cache_oci = f"{doc_ingerido.documento_id}_{'sim' if forcar_simulado_oci else 'real'}"
            if chave_cache_oci not in st.session_state.cache_persistencia_oci:
                res_oci = executar_persistencia_triagem(
                    documento_id=doc_ingerido.documento_id,
                    nome_arquivo=doc_ingerido.nome_arquivo,
                    conteudo_original_bytes=doc_ingerido.conteudo_bytes,
                    dados_triagem_json=triagem_candidata.model_dump(mode="json"),
                    caminho_resultado_alvo=caminho_oci_alvo,
                    forcar_simulado=forcar_simulado_oci,
                    mime_original=resolver_mime_type(doc_ingerido),
                )
                st.session_state.cache_persistencia_oci[chave_cache_oci] = res_oci
            else:
                res_oci = st.session_state.cache_persistencia_oci[chave_cache_oci]

            triagem_final = montar_triagem_canonica(
                documento_id=doc_ingerido.documento_id,
                classificacao=classif_obj,
                dados_extraidos=dados_ext_obj,
                qualidade_wf=qualidade_wf,
                decisao_wf=decisao_wf,
                urgencia_efetiva=urgencia_efetiva,
                res_oci=res_oci,
                caminho_alvo=caminho_oci_alvo,
                modo_simulacao_padrao=forcar_simulado_oci,
            )

            sufixo_persistencia = (
                " *(modo local simulado)*" if res_oci["modo_simulacao"] else " *(confirmado no OCI)*"
            )

            # Card Principal no Topo (nunca declara sucesso se a persistência OCI falhou)
            if res_oci["status_backup"] == "falha":
                with st.container(border=True):
                    st.error(
                        "⚠️ ERRO DE PERSISTÊNCIA NO OCI (`ERRO_PERSISTENCIA`)",
                        icon=":material/cloud_off:",
                    )
                    st.markdown(f"**Mensagem:** {res_oci['erro']}")
                    st.markdown(
                        f"**Roteamento clínico calculado (preservado em memória):** `{destinos_str}`"
                    )
                    st.markdown(f"**Justificativa do Agente:** {decisao_wf.justificativa}")
                    st.caption(
                        "A triagem não é considerada concluída com sucesso enquanto original e resultado não forem confirmados no OCI (EF v1.2 §12 / RF-30)."
                    )
                if eh_urgente and decisao_wf.alerta_simulado:
                    st.warning(
                        "🚨 **ALERTA SIMULADO DE PLANTÃO REGISTRADO**: Sinais de urgência médica identificados — priorizar atendimento clínico imediato (canal lógico simulado no MVP).",
                        icon=":material/notification_important:",
                    )

            elif eh_urgente and requer_auditoria:
                with st.container(border=True):
                    st.error(
                        "🚨 URGÊNCIA CLÍNICA COM REVISÃO HUMANA SIMULTÂNEA (`EM_REVISAO`)",
                        icon=":material/emergency:",
                    )
                    st.markdown("**Destinos Lógicos Simultâneos (RN-08 / Regra R4):**")
                    for idx, nome_dest in enumerate(destinos_nomes, start=1):
                        st.markdown(f"{idx}. **{nome_dest}**")
                    st.markdown(f"**Justificativa do Agente:** {decisao_wf.justificativa}")
                    st.caption(
                        f"📦 Armazenamento OCI: `{caminho_oci_alvo}`{sufixo_persistencia} · Destinos e alertas são lógicos/simulados no MVP."
                    )
                if decisao_wf.alerta_simulado:
                    st.warning(
                        "🚨 **ALERTA SIMULADO AO PLANTÃO**: Evento de urgência registrado com encaminhamento paralelo à fila lógica de revisão humana.",
                        icon=":material/notification_important:",
                    )

            elif eh_urgente and not requer_auditoria:
                with st.container(border=True):
                    st.error(
                        "🚨 CASO CRÍTICO / URGÊNCIA ISOLADA (`PROCESSADO` — RN-08)",
                        icon=":material/emergency:",
                    )
                    st.markdown(f"**Destino Lógico:** `{destinos_str}`")
                    st.markdown(f"**Justificativa do Agente:** {decisao_wf.justificativa}")
                    st.caption(
                        f"📦 Armazenamento OCI: `{caminho_oci_alvo}`{sufixo_persistencia} · Sem ambiguidade, segue sem revisão humana (RN-08). Destinos e alertas simulados no MVP."
                    )
                if decisao_wf.alerta_simulado:
                    st.warning(
                        "🚨 **ALERTA SIMULADO AO PLANTÃO**: Evento de urgência médica registrado em canal lógico simulado (`SIMULADO_SLACK_PLANTAO`).",
                        icon=":material/notification_important:",
                    )

            elif requer_auditoria:
                with st.container(border=True):
                    st.warning(
                        "🧑‍⚕️ ENCAMINHADO À FILA LÓGICA DE REVISÃO HUMANA (`EM_REVISAO`)",
                        icon=":material/assignment_late:",
                    )
                    st.markdown(f"**Destino Lógico:** `{destinos_str}`")
                    st.markdown(f"**Justificativa do Agente:** {decisao_wf.justificativa}")
                    st.caption(
                        f"📦 Armazenamento OCI: `{caminho_oci_alvo}`{sufixo_persistencia} · Fila lógica simulada no MVP."
                    )

            else:
                with st.container(border=True):
                    st.success(
                        "🟢 PROCESSAMENTO AUTÔNOMO CONCLUÍDO — ROTINA (`PROCESSADO`)",
                        icon=":material/verified:",
                    )
                    st.markdown(f"**Destino Lógico:** `{destinos_str}`")
                    st.markdown(f"**Justificativa do Agente:** {decisao_wf.justificativa}")
                    st.caption(
                        f"📦 Armazenamento OCI: `{caminho_oci_alvo}`{sufixo_persistencia} · Destino lógico simulado no MVP."
                    )

            # -----------------------------------------------------------------
            # 3. ABAS DE DETALHAMENTO CLÍNICO E OPERACIONAL
            # -----------------------------------------------------------------
            tab_clinico, tab_hitl, tab_oci, tab_json = st.tabs(
                [
                    ":material/medical_services: Resumo Clínico & Qualidade",
                    ":material/assignment_ind: Fila de Revisão (HITL)",
                    ":material/history: Linha do Tempo & OCI",
                    ":material/data_object: Payload JSON",
                ]
            )

            # --- ABA 1: RESUMO CLÍNICO & QUALIDADE ---
            with tab_clinico:
                if qualidade_wf.motivos_revisao:
                    with st.container(border=True):
                        st.markdown("#### ⚠️ Motivos de Retenção Calculados pelo Agente")
                        for motivo in qualidade_wf.motivos_revisao:
                            st.markdown(f"- 🔸 **{motivo}**")
                        if qualidade_wf.campos_ausentes:
                            st.caption(
                                f"Campos ausentes identificados: `{', '.join(qualidade_wf.campos_ausentes)}`"
                            )

                conflitos_lista = getattr(qualidade_wf, "conflitos", [])
                incertos_lista = getattr(qualidade_wf, "campos_incertos", [])
                if conflitos_lista or incertos_lista:
                    with st.container(border=True):
                        st.markdown("#### ⚡ Sinais Clínicos & Incertezas (Envelope IA)")
                        for conf in conflitos_lista:
                            grav = getattr(conf, "gravidade", "MEDIA")
                            grav_str = getattr(grav, "value", str(grav)).upper()
                            desc = getattr(conf, "descricao", str(conf))
                            badge_icon = "🚨" if grav_str == "ALTA" else ("⚠️" if grav_str == "MEDIA" else "ℹ️")
                            st.markdown(f"- {badge_icon} **[{grav_str}]** {desc}")
                        if incertos_lista:
                            st.caption(f"Campos/sinais incertos: `{', '.join(incertos_lista)}`")

                with st.container(border=True):
                    st.markdown("#### 📊 Avaliação de Qualidade (Regra R5 & Fórmula A3)")
                    indicadores = calcular_indicadores_qualidade_e_roteamento(
                        qualidade_wf=qualidade_wf,
                        decisao_wf=decisao_wf,
                    )
                    sc1, sc2, sc3, sc4 = st.columns(4)
                    sc1.metric(
                        "Score Combinado",
                        f"{indicadores.score_combinado:.2f}",
                        delta=indicadores.delta_score,
                        delta_color=indicadores.delta_score_cor,
                        help=(
                            "Regra R5: min(Classificação, Extração), onde Extração aplica a "
                            f"Fórmula A3. Limiar aplicado: {indicadores.limiar_aplicado:.2f}"
                        ),
                    )
                    sc2.metric("Classificação", f"{indicadores.score_classificacao:.2f}")
                    sc3.metric("Extração (A3)", f"{indicadores.score_extracao:.2f}")
                    sc4.metric(
                        "Revisão Humana",
                        indicadores.revisao_humana_status,
                        delta=indicadores.revisao_humana_motivo,
                        delta_color=indicadores.revisao_humana_cor,
                        help="Decisão determinística conforme regras R1-R8 e RN-08.",
                    )

                    if indicadores.requer_atencao_mista and indicadores.aviso_misto:
                        st.info(indicadores.aviso_misto, icon=":material/info:")

                with st.container(border=True):
                    st.markdown("#### 📋 Dados Clínicos Extraídos (Fidelidade Estrita — RF-15)")
                    p_obj = dados_ext_obj.paciente
                    m_obj = dados_ext_obj.medico
                    crm_fmt = (
                        m_obj.crm.formatado()
                        if isinstance(m_obj.crm, Crm) and m_obj.crm.numero
                        else (str(m_obj.crm) if m_obj.crm else None)
                    )
                    esp_fmt = ", ".join(classif_obj.especialidade) if classif_obj.especialidade else None

                    info_col1, info_col2 = st.columns(2)
                    with info_col1:
                        st.write(f"**Paciente:** {_formatar_ausente(p_obj.nome)}")
                        st.write(
                            f"**Idade:** {f'{p_obj.idade} anos' if p_obj.idade is not None else 'Não identificado no documento'}"
                        )
                        st.write(f"**Médico Solicitante:** {_formatar_ausente(m_obj.nome)}")
                        st.write(f"**CRM:** {_formatar_ausente(crm_fmt)}")
                    with info_col2:
                        tipo_exib = getattr(classif_obj.tipo_documento, "value", str(classif_obj.tipo_documento))
                        prio_exib = getattr(classif_obj.nivel_prioridade, "value", str(classif_obj.nivel_prioridade))
                        urg_exib = getattr(dados_ext_obj.urgencia, "value", str(dados_ext_obj.urgencia))
                        st.write(f"**Tipo Documental:** `{tipo_exib}`")
                        st.write(f"**Especialidade:** {_formatar_ausente(esp_fmt)}")
                        st.write(f"**Prioridade / Sinal Urgência:** `{prio_exib}` / `{urg_exib}`")
                        st.write(f"**CID-10 Explícito:** {_formatar_ausente(dados_ext_obj.cid)}")

                    st.write(f"**Diagnóstico / Hipótese:** {_formatar_ausente(dados_ext_obj.diagnostico)}")

                    if dados_ext_obj.medicamentos:
                        st.markdown("**Medicamentos Prescritos:**")
                        for med in dados_ext_obj.medicamentos:
                            if hasattr(med, "nome"):
                                dose = getattr(med, "dosagem", None) or "dose não informada"
                                freq = getattr(med, "frequencia", None) or "frequência não informada"
                                st.write(f"- 💊 **{med.nome}** — {dose} ({freq})")
                            else:
                                st.write(f"- 💊 {med}")

                    if dados_ext_obj.exames:
                        st.markdown("**Exames Identificados:**")
                        for exame in dados_ext_obj.exames:
                            st.write(f"- 🧪 {exame}")

                    if dados_ext_obj.exames_laboratoriais:
                        st.markdown("**Parâmetros Laboratoriais (RF-12):**")
                        for item in dados_ext_obj.exames_laboratoriais:
                            unid = f" {item.unidade}" if item.unidade else ""
                            ref = f" (Ref.: {item.referencia_impressa})" if item.referencia_impressa else ""
                            st.write(f"- 🔬 **{item.analito}:** {item.valor_medido}{unid}{ref}")

            # --- ABA 2: FILA LÓGICA DE REVISÃO HUMANA (ESCOPO MVP — EF v1.2 §15.7) ---
            with tab_hitl:
                with st.container(border=True):
                    st.markdown("#### 🧑‍⚕️ Fila Lógica de Revisão Humana (`FILA_REVISAO_HUMANA`)")
                    regras_str = ", ".join(getattr(decisao_wf, "regras_acionadas", []) or []) or "NENHUMA"

                    if requer_auditoria:
                        st.warning(
                            "Este documento encontra-se retido na **Fila Lógica de Revisão Humana** (`status = EM_REVISAO`).",
                            icon=":material/assignment_late:",
                        )
                        obrigatorios_faltantes = sorted(
                            set(qualidade_wf.campos_ausentes or []) & set(CAMPOS_OBRIGATORIOS)
                        )
                        impeditivos = [
                            c
                            for c in (getattr(qualidade_wf, "conflitos", None) or [])
                            if str(getattr(c.gravidade, "value", c.gravidade)).upper() in GRAVIDADES_IMPEDITIVAS
                        ]

                        st.markdown(f"- **Regras Acionadas:** `{regras_str}`")
                        st.markdown(f"- **Destinos Registrados:** `{', '.join(destinos_raw)}`")
                        st.markdown(f"- **Prefixo de Segregação OCI:** `auditoria_humana/{doc_ingerido.documento_id}/resultado.json`")

                        if obrigatorios_faltantes:
                            st.markdown(
                                f"- **Campos Obrigatórios Ausentes (RF-21):** `{', '.join(obrigatorios_faltantes)}`"
                            )
                        if qualidade_wf.campos_incertos:
                            st.markdown(
                                f"- **Campos / Sinais Incertos:** `{', '.join(qualidade_wf.campos_incertos)}`"
                            )
                        if impeditivos:
                            tipos_imp = ", ".join(c.tipo for c in impeditivos)
                            st.markdown(f"- **Conflitos Impeditivos (`ALTA`/`MEDIA`):** `{tipos_imp}`")

                        st.markdown("**Motivos Detalhados para o Auditor:**")
                        for motivo in qualidade_wf.motivos_revisao:
                            st.markdown(f"  - {motivo}")
                    elif eh_urgente:
                        st.info(
                            "**Revisão Humana Dispensada (RN-08 — Urgência Isolada):** "
                            "O caso possui urgência médica confirmada sem ambiguidade, ilegibilidade, conflito impeditivo, "
                            "ausência de campo obrigatório ou score abaixo do limiar. Segue exclusivamente para "
                            "`FILA_URGENCIA_MEDICA` com status `PROCESSADO` e alerta simulado.",
                            icon=":material/emergency:",
                        )
                    else:
                        st.success(
                            f"**Revisão Humana Dispensada (Rotina Aprovada):** Score combinado "
                            f"`{qualidade_wf.score_combinado:.2f}` ≥ limiar `{qualidade_wf.limiar_aplicado:.2f}`, "
                            f"campos vitais presentes e sem conflitos impeditivos (Regras: `{regras_str}`).",
                            icon=":material/check_circle:",
                        )

                    st.caption(
                        "Delimitação do MVP (EF v1.2 §4, §5.3, §11.9 e §15.7): a Fila de Revisão Humana é lógica/simulada. "
                        "Os dados extraídos permanecem íntegros conforme o documento original, sem edição ou aprovação manual pela interface."
                    )

            # --- ABA 3: LINHA DO TEMPO & SNAPSHOTS OCI ---
            with tab_oci:
                with st.container(border=True):
                    st.markdown("#### ☁️ Armazenamento & Segregação OCI Always Free")
                    st.markdown(f"**Bucket OCI:** `{res_oci['bucket']}`")
                    st.markdown(f"**Caminho do Original:** `{res_oci['caminho_original']}`")
                    caminho_exibido = (
                        res_oci["caminho_objeto"]
                        if res_oci.get("caminho_objeto")
                        else f"{res_oci['caminho_alvo']} (gravação não confirmada)"
                    )
                    st.markdown(f"**Caminho do Resultado:** `{caminho_exibido}`")

                    if res_oci["status_backup"] == "sucesso":
                        st.success(
                            "**Persistência Confirmada no OCI Object Storage!**\n\n"
                            f"- **ETag:** `{res_oci.get('etag') or 'Confirmado'}`\n"
                            "- **Integridade:** Documento original e JSON de resultado gravados sem sobrescrita (`if-none-match: *`).",
                            icon=":material/cloud_done:",
                        )
                    elif res_oci["status_backup"] == "falha":
                        st.error(
                            "**Falha na Persistência com o OCI Object Storage:**\n\n"
                            f"- **Mensagem:** {res_oci['erro']}\n\n"
                            "> Os detalhes técnicos da falha foram registrados exclusivamente nos logs internos para diagnóstico seguro.",
                            icon=":material/cloud_off:",
                        )
                    else:
                        st.warning(
                            "**Persistência em Modo Simulado / Local:**\n\n"
                            f"- **Detalhe:** {res_oci['detalhes']}\n\n"
                            "> Nenhum objeto externo foi gravado no bucket da Oracle Cloud nesta execução.",
                            icon=":material/cloud_sync:",
                        )

                with st.container(border=True):
                    st.markdown("#### 🕒 Linha do Tempo do Ciclo de Vida Documental")
                    st.markdown("1. 📥 **RECEBIDO** — Documento validado e aceito na ingestão.")
                    st.markdown("2. 🧠 **PROCESSANDO** — Classificação, extração e avaliação determinística no LangGraph.")
                    st.markdown(
                        f"3. ⚖️ **ROTEADO** — Destino lógico `{destinos_str}` (Score combinado: `{qualidade_wf.score_combinado:.2f}`)."
                    )
                    if res_oci["status_backup"] == "falha":
                        st.markdown(
                            "4. ⚠️ **ERRO_PERSISTENCIA** — Gravação durável no OCI não confirmada; decisão clínica preservada em memória."
                        )
                    elif requer_auditoria:
                        st.markdown(
                            f"4. ⏳ **EM_REVISAO** — Retido na fila lógica (`{res_oci['evento_linha_do_tempo']}`)."
                        )
                    else:
                        st.markdown(
                            f"4. ✅ **PROCESSADO** — Fluxo automático concluído (`{res_oci['evento_linha_do_tempo']}`)."
                        )

            # --- ABA 4: PAYLOAD JSON CANÔNICO (TriagemMediFlow) ---
            with tab_json:
                payload_saida = triagem_final.model_dump(mode="json")
                st.json(payload_saida)

else:
    st.info(
        "👈 Selecione um cenário de demonstração ou envie um documento clínico na barra lateral para iniciar a triagem.",
        title="Aguardando Seleção",
    )
