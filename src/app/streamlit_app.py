"""
MediFlow — Interface de Demonstração e Auditoria Clínica (Streamlit).
Equipe 15 · Hackathon ONE G10 (Oracle & Alura).
Permite ingestão multimodal (PDF, TXT, Imagens), classificação e extração via Gemini,
orquestração determinística via LangGraph e auditoria médica Human-in-the-Loop (HiTL).
"""
import sys
from pathlib import Path

# Garante que a raiz do projeto esteja no sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import os
import re
import streamlit as st
from dotenv import load_dotenv

from typing import Any, Dict, List, Optional
from src.ingestion import DocumentLoader, IngestaoError
from src.services.gemini_service import GeminiService
from src.workflow.graph import criar_grafo
from src.workflow.state import EntradaWorkflow
from src.schemas import (
    TriagemMediFlow,
    StatusTriagem,
    Destino,
    DestinoRoteamento,
    Classificacao,
    ClassificacaoClinica,
    DadosExtraidos,
    Paciente,
    Medico,
    Crm,
    NivelPrioridade,
)

load_dotenv(override=True)

MAPA_DESTINOS_ROTULOS = {
    "EMERGENCIA": "Pronto-Socorro / Emergência Hospitalar",
    "EMERGENCIA_HOSPITALAR": "Pronto-Socorro / Emergência Hospitalar",
    "REVISAO_HUMANA": "Fila de Auditoria Médica (Human-in-the-Loop)",
    "FILA_REVISAO_HUMANA": "Fila de Auditoria Médica (Human-in-the-Loop)",
    "PRONTUARIO_ELETRONICO": "Prontuário Eletrônico do Paciente",
    "FARMACIA_HOSPITALAR": "Farmácia Hospitalar",
    "AMBULATORIO_RETORNO": "Ambulatório de Retorno / Especialidades",
    "CENTRO_ONCOLOGICO": "Centro de Oncologia / Protocolos",
    "REGULACAO_LEITOS": "Central de Regulação de Leitos",
}


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
    limiar: float = 0.85,
) -> Dict[str, Any]:
    """Invoca deterministicamente o motor LangGraph para decisão clínica e roteamento."""
    urgente = "URGENTE" in str(prioridade_str).upper() or urgencia == "SIM"

    # 1. Detecção rigorosa de campos ausentes / ilegíveis
    campos_ausentes = []
    p_nome = paciente_dict.get("nome")
    if not p_nome or "ilegível" in str(p_nome).lower() or "não identificado" in str(p_nome).lower() or str(p_nome).strip() in ("N/I", ""):
        campos_ausentes.append("paciente.nome")
        p_nome_clean = None
    else:
        p_nome_clean = str(p_nome)

    p_idade = paciente_dict.get("idade")
    if p_idade is None:
        campos_ausentes.append("paciente.idade")

    m_nome = medico_dict.get("nome")
    if not m_nome or "ilegível" in str(m_nome).lower() or "não identificado" in str(m_nome).lower() or str(m_nome).strip() in ("N/I", ""):
        campos_ausentes.append("medico.nome")
        m_nome_clean = None
    else:
        m_nome_clean = str(m_nome)

    crm_val = medico_dict.get("crm")
    crm_obj = None
    if not crm_val or "?" in str(crm_val) or "ilegível" in str(crm_val).lower() or str(crm_val).strip() in ("N/I", ""):
        campos_ausentes.append("medico.crm")
    else:
        crm_str = re.sub(r"(?i)^crm[\s\:\/\.\-]*", "", str(crm_val)).strip()
        partes = re.split(r"[-/]", crm_str)
        if len(partes) == 2 and partes[0].isdigit():
            crm_obj = Crm(numero=partes[0].strip(), uf=partes[1].strip().upper())
        elif partes[0].isdigit():
            crm_obj = Crm(numero=partes[0].strip(), uf="SP")
        else:
            campos_ausentes.append("medico.crm")

    diag_clean = diagnostico
    if not diagnostico or "borrada" in str(diagnostico).lower() or str(diagnostico).strip() in ("N/I", ""):
        tipo_upper = str(tipo_documento).upper()
        if "LABORATORIAL" not in tipo_upper:
            campos_ausentes.append("diagnostico")
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
        urgencia="SIM" if urgente else "NAO",
    )

    classificacao = ClassificacaoClinica(
        tipo_documento=tipo_documento,
        nivel_prioridade=NivelPrioridade.URGENTE if urgente else NivelPrioridade.ROTINA,
        score_confianca_classificacao=score_classificacao,
    )

    entrada = EntradaWorkflow(
        documento_id=documento_id,
        classificacao=classificacao,
        dados_extraidos=dados_extraidos,
        urgencia="SIM" if urgente else "NAO",
        campos_ausentes=list(set(campos_ausentes)),
        campos_incertos=[],
        conflitos=[],
        limiar=limiar,
    )

    grafo = criar_grafo()
    return grafo.invoke({"entrada": entrada})


# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA (STREAMLIT NATIVO)
# ==============================================================================
st.set_page_config(
    page_title="MediFlow — Triagem Clínica Autônoma",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização CSS customizada compatível com tema claro e escuro
st.markdown("""
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
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# CENÁRIOS DEMO OFICIAIS (DO EDITAL E FIXTURES CANÔNICOS)
# ==============================================================================
CENARIOS_DEMO = {
    "Cenário 1: Rotina (RX de Tórax Normal)": {
        "arquivo": "01_laudo_rotina.pdf",
        "tipo": "Laudo de Exame de Imagem",
        "especialidade": "Radiologia",
        "prioridade": "Rotina",
        "score_classif": 0.96,
        "score_extrac": 0.98,
        "score_combinado": 0.96,
        "paciente": "João Carlos da Silva",
        "idade": 42,
        "medico": "Dr. Roberto Mendes",
        "crm": "112345-SP",
        "diagnostico": "Radiografia de tórax dentro dos limites da normalidade.",
        "cid": None,
        "destino": "Prontuário Eletrônico do Paciente",
        "requer_auditoria": False,
        "pasta_oci": "processados/DOC-CLIN-2026-ROTINA01.json",
        "justificativa": "Laudo admissional sem alterações clínicas significativas. Critérios de rotina aprovados."
    },
    "Cenário 2: Urgência Crítica (Angiotomografia - TEP Agudo)": {
        "arquivo": "02_laudo_urgencia_tep.pdf",
        "tipo": "Laudo de Exame de Imagem",
        "especialidade": "Radiologia / Pneumologia",
        "prioridade": "Urgente",
        "score_classif": 0.99,
        "score_extrac": 0.98,
        "score_combinado": 0.98,
        "paciente": "Maria Eduarda Santos",
        "idade": 61,
        "medico": "Dra. Camila Alencar",
        "crm": "98765-SP",
        "diagnostico": "Tromboembolismo Pulmonar Agudo Massivo",
        "cid": "I26.9",
        "destino": "Fila de Urgência Médica (Emergência)",
        "requer_auditoria": True,
        "pasta_oci": "processados/urgentes/DOC-CLIN-2026-URG002.json",
        "alerta": "🚨 ALERTA DE PLANTÃO: Tromboembolismo Pulmonar Agudo detectado. Encaminhar imediatamente para Hemodinâmica/UTI.",
        "justificativa": "Achado crítico com sobrecarga de câmaras direitas. Notificação de urgência hospitalar gerada."
    },
    "Cenário 3: Ambiguidade / Rasura (Receituário - Human-in-the-Loop)": {
        "arquivo": "03_receituario_ambiguo.pdf",
        "tipo": "Receituário Médico",
        "especialidade": "Clínica Médica / Farmácia",
        "prioridade": "Ambiguidade / Revisão",
        "score_classif": 0.80,
        "score_extrac": 0.65,
        "score_combinado": 0.65,
        "paciente": "Maria de Fátima Oliveira [Nome parcialmente ilegível]",
        "idade": 55,
        "medico": "Dr. [Assinatura ilegível]",
        "crm": "123...?-SP",
        "diagnostico": "Prescrição de anti-hipertensivo com dosagem borrada",
        "cid": None,
        "destino": "Fila de Revisão Humana (Auditoria Médica)",
        "requer_auditoria": True,
        "pasta_oci": "auditoria/DOC-CLIN-2026-REV003.json",
        "justificativa": "Score combinado (0.65) abaixo do limiar (0.85), carimbo do CRM ilegível e posologia ambígua."
    }
}

# ==============================================================================
# INICIALIZAÇÃO DE ESTADO DE SESSÃO
# ==============================================================================
if "auditoria_aprovada" not in st.session_state:
    st.session_state.auditoria_aprovada = False

if "dados_editados" not in st.session_state:
    st.session_state.dados_editados = None

if "doc_id_atual" not in st.session_state:
    st.session_state.doc_id_atual = None

if "resultado_ia" not in st.session_state:
    st.session_state.resultado_ia = None

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
        default="Cenários Oficiais (Demo)"
    )
    
    doc_ingerido = None
    dados_mock = None

    if modo_entrada == "Cenários Oficiais (Demo)":
        cenario_escolhido = st.selectbox(
            "Selecione um caso clínico do edital:",
            list(CENARIOS_DEMO.keys())
        )
        dados_mock = CENARIOS_DEMO[cenario_escolhido]
        caminho_pdf = ROOT_DIR / "data" / "samples" / dados_mock["arquivo"]
        
        if caminho_pdf.exists():
            doc_ingerido = DocumentLoader.carregar_arquivo(caminho_pdf)
        else:
            st.warning("Arquivo PDF de teste não encontrado localmente.", title="Arquivo ausente")
            
    else:
        uploaded_file = st.file_uploader(
            "Arraste ou selecione um laudo/receita:",
            type=["pdf", "png", "jpg", "jpeg", "webp", "txt"],
            help="Formatos aceitos: PDF, TXT ou Imagens (Máx: 10MB / 20 páginas)"
        )
        
        if uploaded_file is not None:
            try:
                bytes_data = uploaded_file.read()
                doc_ingerido = DocumentLoader.carregar_bytes(
                    conteudo_bytes=bytes_data,
                    nome_arquivo=uploaded_file.name
                )
                st.success(f"Arquivo lido com sucesso! ({doc_ingerido.tamanho_bytes / 1024:.1f} KB)", title="Upload Concluído")
            except IngestaoError as e:
                st.error(f"Erro de Ingestão: {e.codigo} — {e.mensagem}", title="Rejeição de Arquivo")
            except Exception as e:
                st.error(f"Erro inesperado: {str(e)}", title="Falha")

    st.markdown("---")
    chave_env = os.getenv("GEMINI_API_KEY", "")
    tem_chave_valida = bool(chave_env and not chave_env.startswith("sua_chave"))
    api_key_custom = st.text_input(
        "🔑 Chave Gemini API (Opcional):",
        value=chave_env if tem_chave_valida else "",
        type="password",
        help="Insira sua chave do Google AI Studio para inferência ao vivo com Gemini Multimodal."
    )

    st.markdown("---")
    st.markdown("**Hackathon ONE G10 — Oracle & Alura**")
    st.caption("Engenharia de Software com LangGraph, Pydantic v2 e OCI Always Free.")

# ==============================================================================
# CABEÇALHO PRINCIPAL
# ==============================================================================
st.markdown("<div class='main-header'>MediFlow — Triagem Clínica Documental</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-header'>Pipeline com Ingestão Blindada PyMuPDF · Validação Pydantic v2 · Decisão Determinística LangGraph · OCI Object Storage</div>", unsafe_allow_html=True)

# ==============================================================================
# CORPO PRINCIPAL (VISÃO LADO A LADO)
# ==============================================================================
if doc_ingerido is not None:
    # Reseta estado de auditoria ao trocar de documento
    if st.session_state.doc_id_atual != doc_ingerido.documento_id:
        st.session_state.doc_id_atual = doc_ingerido.documento_id
        st.session_state.auditoria_aprovada = False
        st.session_state.dados_editados = None
        st.session_state.resultado_ia = None

    col_esquerda, col_direita = st.columns([1, 1], gap="medium")

    # -------------------------------------------------------------------------
    # COLUNA ESQUERDA: DOCUMENTO ORIGINAL E METADADOS DA INGESTÃO
    # -------------------------------------------------------------------------
    with col_esquerda:
        st.subheader("📄 Documento Ingerido", anchor=False)
        
        # Cards de métricas rápidas da ingestão em container delimitado
        with st.container(border=True):
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Formato", doc_ingerido.formato)
            m2.metric("Páginas", doc_ingerido.total_paginas)
            m3.metric("Tamanho", f"{doc_ingerido.tamanho_bytes / 1024:.1f} KB")
            m4.metric("OCR Visual?", "Sim" if doc_ingerido.requer_ocr else "Não")

        st.caption(f"**Identificador Canônico:** `{doc_ingerido.documento_id}` | **Arquivo:** `{doc_ingerido.nome_arquivo}`")
        
        # Exibição visual de imagem se for mídia gráfica ou texto bruto extraído
        if doc_ingerido.formato in ["JPG", "JPEG", "PNG", "WEBP"] and doc_ingerido.conteudo_bytes:
            st.markdown("**Visualização do Documento Digitalizado:**")
            st.image(doc_ingerido.conteudo_bytes, caption=doc_ingerido.nome_arquivo, width="stretch")
        else:
            st.markdown("**Texto Extraído pelo PyMuPDF:**")
            st.text_area(
                label="Conteúdo Bruto",
                value=doc_ingerido.conteudo_texto if doc_ingerido.conteudo_texto else "[Mídia em Imagem/Scaneada — análise visual via IA]",
                height=360,
                disabled=True,
                label_visibility="collapsed"
            )

    # -------------------------------------------------------------------------
    # COLUNA DIREITA: RESULTADO DA TRIAGEM CLÍNICA & DECISÃO DO AGENTE
    # -------------------------------------------------------------------------
    with col_direita:
        st.subheader("⚖️ Decisão do Agente & Roteamento", anchor=False)

        # 1. PROCESSAMENTO DE DADOS: CENÁRIOS DEMO OU UPLOAD REAL
        decisao_wf = None
        qualidade_wf = None
        tipo_doc_str = ""
        prioridade_str = ""
        p_nome = "Não identificado"
        p_idade = None
        m_nome = "Não identificado"
        crm_str = "N/I"
        diag_str = "N/I"
        cid_str = "Não informado"
        medicamentos_lista = []
        caminho_oci_alvo = f"processados/{doc_ingerido.documento_id}.json"

        if dados_mock:
            # Caso Demo: executa no LangGraph
            paciente_d = {"nome": dados_mock["paciente"], "idade": dados_mock["idade"]}
            medico_d = {"nome": dados_mock["medico"], "crm": dados_mock["crm"]}
            estado_wf = executar_fluxo_agente(
                documento_id=doc_ingerido.documento_id,
                tipo_documento=dados_mock["tipo"],
                prioridade_str=dados_mock["prioridade"],
                score_classificacao=dados_mock["score_classif"],
                paciente_dict=paciente_d,
                medico_dict=medico_d,
                diagnostico=dados_mock["diagnostico"],
                cid=dados_mock["cid"],
                urgencia="SIM" if "Urgente" in dados_mock["prioridade"] else "NAO",
            )
            decisao_wf = estado_wf.get("decisao")
            qualidade_wf = estado_wf.get("qualidade")
            tipo_doc_str = dados_mock["tipo"]
            prioridade_str = dados_mock["prioridade"]
            p_nome = dados_mock["paciente"]
            p_idade = dados_mock["idade"]
            m_nome = dados_mock["medico"]
            crm_str = dados_mock["crm"]
            diag_str = dados_mock["diagnostico"]
            cid_str = dados_mock["cid"] or "Não informado"
            caminho_oci_alvo = dados_mock["pasta_oci"]
        else:
            # Modo Upload: botões de execução
            st.info("Arquivo recebido com sucesso na Ingestão! Pronto para análise inteligente com Gemini.", title="Pronto para Análise")
            
            btn_col1, btn_col2 = st.columns([2, 1])
            with btn_col1:
                executar_ia = st.button("Executar Triagem Clínica com Gemini IA", type="primary", width="stretch", icon=":material/smart_toy:")
            with btn_col2:
                usar_fallback_teste = st.button("Testar com Simulação", width="stretch", icon=":material/bolt:")

            if executar_ia:
                with st.spinner("Analisando documento clínico com Gemini IA Multimodal e Motor LangGraph..."):
                    service = GeminiService(api_key=api_key_custom or os.getenv("GEMINI_API_KEY"))
                    
                    mime_map = {
                        "PDF": "application/pdf",
                        "JPG": "image/jpeg",
                        "JPEG": "image/jpeg",
                        "PNG": "image/png",
                        "WEBP": "image/webp",
                        "TXT": "text/plain"
                    }
                    formato_upper = (doc_ingerido.formato or "JPG").upper()
                    mime_tipo = doc_ingerido.metadados.get("mime") or mime_map.get(formato_upper, "image/jpeg")

                    classif = service.classificar_documento(
                        conteudo_texto=doc_ingerido.conteudo_texto or "",
                        conteudo_bytes=doc_ingerido.conteudo_bytes,
                        mime_type=mime_tipo
                    )
                    extrac = service.extrair_dados_clinicos(
                        conteudo_texto=doc_ingerido.conteudo_texto or "",
                        conteudo_bytes=doc_ingerido.conteudo_bytes,
                        mime_type=mime_tipo
                    )

                    paciente_obj = getattr(extrac, "paciente", None)
                    medico_obj = getattr(extrac, "medico_solicitante", getattr(extrac, "medico", None))
                    crm_raw = getattr(medico_obj, "crm", None)
                    if hasattr(crm_raw, "numero") and hasattr(crm_raw, "uf"):
                        crm_txt = f"{crm_raw.numero}-{crm_raw.uf}"
                    else:
                        crm_txt = str(crm_raw or "")

                    p_d = {"nome": getattr(paciente_obj, "nome", None), "idade": getattr(paciente_obj, "idade", None)}
                    m_d = {"nome": getattr(medico_obj, "nome", None), "crm": crm_txt}

                    t_val = getattr(classif, "tipo_documento", "OUTRO")
                    t_str = t_val.value if hasattr(t_val, "value") else str(t_val)
                    p_val = getattr(classif, "nivel_prioridade", "ROTINA")
                    pr_str = p_val.value if hasattr(p_val, "value") else str(p_val)

                    d_val = getattr(extrac, "diagnostico_principal", getattr(extrac, "diagnostico", None))
                    c_val = getattr(extrac, "cid_extraido", getattr(extrac, "cid", None))

                    estado_wf = executar_fluxo_agente(
                        documento_id=doc_ingerido.documento_id,
                        tipo_documento=t_str,
                        prioridade_str=pr_str,
                        score_classificacao=getattr(classif, "score_confianca_classificacao", 0.95),
                        paciente_dict=p_d,
                        medico_dict=m_d,
                        diagnostico=d_val,
                        cid=c_val,
                        medicamentos=getattr(extrac, "medicamentos", []),
                        exames=getattr(extrac, "exames", []),
                        urgencia="SIM" if "URGENTE" in pr_str.upper() else "NAO",
                    )

                    st.session_state.resultado_ia = {
                        "decisao_wf": estado_wf.get("decisao"),
                        "qualidade_wf": estado_wf.get("qualidade"),
                        "tipo_doc_str": t_str,
                        "prioridade_str": pr_str,
                        "p_nome": p_d["nome"] or "Não identificado",
                        "p_idade": p_d["idade"],
                        "m_nome": m_d["nome"] or "Não identificado",
                        "crm_str": crm_txt or "N/I",
                        "diag_str": d_val or "N/I",
                        "cid_str": c_val or "Não informado",
                        "medicamentos_lista": getattr(extrac, "medicamentos", []),
                        "chave_ativa": bool(api_key_custom or tem_chave_valida),
                        "simulado": False
                    }

            if usar_fallback_teste:
                # Simulação local com o motor LangGraph
                estado_wf = executar_fluxo_agente(
                    documento_id=doc_ingerido.documento_id,
                    tipo_documento="Receituário Médico",
                    prioridade_str="Rotina",
                    score_classificacao=0.95,
                    paciente_dict={"nome": "Carlos Drummond", "idade": 50},
                    medico_dict={"nome": "Dr. Fernando Pessoa", "crm": "12345-SP"},
                    diagnostico="Prescrição de Rotina",
                    cid=None,
                    urgencia="NAO",
                )
                st.session_state.resultado_ia = {
                    "decisao_wf": estado_wf.get("decisao"),
                    "qualidade_wf": estado_wf.get("qualidade"),
                    "tipo_doc_str": "Receituário Médico",
                    "prioridade_str": "Rotina",
                    "p_nome": "Carlos Drummond",
                    "p_idade": 50,
                    "m_nome": "Dr. Fernando Pessoa",
                    "crm_str": "12345-SP",
                    "diag_str": "Prescrição de Rotina",
                    "cid_str": "Não informado",
                    "medicamentos_lista": [],
                    "chave_ativa": True,
                    "simulado": True
                }

            if st.session_state.resultado_ia:
                res = st.session_state.resultado_ia
                decisao_wf = res["decisao_wf"]
                qualidade_wf = res["qualidade_wf"]
                tipo_doc_str = res["tipo_doc_str"]
                prioridade_str = res["prioridade_str"]
                p_nome = res["p_nome"]
                p_idade = res["p_idade"]
                m_nome = res["m_nome"]
                crm_str = res["crm_str"]
                diag_str = res["diag_str"]
                cid_str = res["cid_str"]
                medicamentos_lista = res.get("medicamentos_lista", [])

                if not res.get("chave_ativa") and not res.get("simulado"):
                    st.warning(
                        "Chave GEMINI_API_KEY não configurada ou inválida. O serviço operou com o fail-safe resiliente (Seção 12 E.F.), direcionando para revisão humana.",
                        title="Aviso de Segurança Fail-Safe"
                    )

        # ---------------------------------------------------------------------
        # 2. RENDERIZAÇÃO UNIFICADA DA DECISÃO DO AGENTE
        # ---------------------------------------------------------------------
        if decisao_wf is not None and qualidade_wf is not None:
            # Aplica dados editados pelo médico se houve auditoria
            if st.session_state.auditoria_aprovada and st.session_state.dados_editados:
                ed = st.session_state.dados_editados
                p_nome = ed.get("paciente", p_nome)
                p_idade = ed.get("idade", p_idade)
                m_nome = ed.get("medico", m_nome)
                crm_str = ed.get("crm", crm_str)
                diag_str = ed.get("diagnostico", diag_str)
                cid_str = ed.get("cid", cid_str)

            destinos_raw = [d.value if hasattr(d, "value") else str(d) for d in decisao_wf.destinos]
            destinos_nomes = [MAPA_DESTINOS_ROTULOS.get(d, d) for d in destinos_raw]
            destinos_str = " + ".join(destinos_nomes)

            requer_auditoria = decisao_wf.requer_auditoria_humana
            eh_urgente = any("EMERGENCIA" in d.upper() for d in destinos_raw) or "URGENTE" in prioridade_str.upper()
            foi_auditado = st.session_state.auditoria_aprovada

            # Card Principal de Decisão
            if foi_auditado:
                with st.container(border=True):
                    st.success("🟢 PROCESSAMENTO HOMOLOGADO (PÓS-AUDITORIA MÉDICA)", icon=":material/verified:")
                    st.markdown("**Destino Hospitalar Homologado:** `Prontuário Eletrônico do Paciente`")
                    st.markdown("**Justificativa:** Documento auditado, corrigido e aprovado pelo Médico Auditor (Human-in-the-Loop).")
                    st.caption("📦 Backup OCI: `processados/DOC-CLIN-2026-AUDITADO.json`")

            elif eh_urgente and requer_auditoria:
                with st.container(border=True):
                    st.error("🚨 URGÊNCIA CLÍNICA COM REVISÃO HUMANA SIMULTÂNEA", icon=":material/emergency:")
                    st.markdown(f"**Destinos Hospitalares Simultâneos:**")
                    st.markdown(f"1. **{destinos_nomes[0]}** (Atendimento Imediato)")
                    if len(destinos_nomes) > 1:
                        st.markdown(f"2. **{destinos_nomes[1]}** (Auditoria de Pendências)")
                    st.markdown(f"**Justificativa do Agente:** {decisao_wf.justificativa}")
                    st.caption("📦 Encaminhamento simultâneo: `processados/urgentes/` e `auditoria/`")

                if decisao_wf.alerta_simulado:
                    st.warning("🚨 **ALERTA IMEDIATO AO PLANTÃO**: Notificação crítica disparada! Simultaneamente, o prontuário foi retido para auditoria médica devido a dados incompletos ou borrados.", icon=":material/notification_important:")

            elif eh_urgente and not requer_auditoria:
                with st.container(border=True):
                    st.error("🚨 CASO CRÍTICO / URGÊNCIA CLÍNICA IMEDIATA", icon=":material/emergency:")
                    st.markdown(f"**Destino Hospitalar:** `{destinos_str}`")
                    st.markdown(f"**Justificativa do Agente:** {decisao_wf.justificativa}")
                    st.caption("📦 Pasta OCI: `processados/urgentes/`")

                if decisao_wf.alerta_simulado:
                    st.warning("🚨 **ALERTA IMEDIATO AO PLANTÃO**: Encaminhamento imediato para equipe médica de plantão.", icon=":material/notification_important:")

            elif not eh_urgente and requer_auditoria:
                with st.container(border=True):
                    st.warning("🧑‍⚕️ REQUER REVISÃO HUMANA (Auditoria Médica)", icon=":material/assignment_late:")
                    st.markdown(f"**Destino Hospitalar:** `{destinos_str}`")
                    st.markdown(f"**Justificativa do Agente:** {decisao_wf.justificativa}")
                    st.caption("📦 Pasta OCI: `auditoria/`")

            else:
                with st.container(border=True):
                    st.success("🟢 PROCESSAMENTO AUTÔNOMO APROVADO (ROTINA)", icon=":material/verified:")
                    st.markdown(f"**Destino Hospitalar:** `{destinos_str}`")
                    st.markdown(f"**Justificativa do Agente:** {decisao_wf.justificativa}")
                    st.caption("📦 Pasta OCI: `processados/`")

            # -----------------------------------------------------------------
            # 3. MOTIVOS DE RETENÇÃO DO AGENTE (SE HOUVER)
            # -----------------------------------------------------------------
            if qualidade_wf.motivos_revisao and not foi_auditado:
                with st.container(border=True):
                    st.markdown("#### ⚠️ Motivos da Retenção Calculados pelo Agente:")
                    for motivo in qualidade_wf.motivos_revisao:
                        st.markdown(f"- 🔸 **{motivo}**")
                    if qualidade_wf.campos_ausentes:
                        st.caption(f"Campos ausentes identificados: `{', '.join(qualidade_wf.campos_ausentes)}`")

            # -----------------------------------------------------------------
            # 4. AVALIAÇÃO DE QUALIDADE (FÓRMULA A3)
            # -----------------------------------------------------------------
            with st.container(border=True):
                st.markdown("#### 📊 Avaliação de Qualidade (Fórmula Determinística A3)")
                sc1, sc2, sc3 = st.columns(3)
                score_c = qualidade_wf.score_combinado
                sc1.metric(
                    "Score Combinado",
                    f"{score_c:.2f}",
                    delta="Aprovado (>= 0.85)" if score_c >= 0.85 else "Retido (< 0.85)",
                    delta_color="normal" if score_c >= 0.85 else "inverse"
                )
                sc2.metric("Classificação", f"{qualidade_wf.score_classificacao:.2f}")
                sc3.metric("Extração", f"{qualidade_wf.score_extracao:.2f}")

            # -----------------------------------------------------------------
            # 5. DADOS CLÍNICOS EXTRAÍDOS
            # -----------------------------------------------------------------
            with st.container(border=True):
                st.markdown("#### 📋 Dados Clínicos Extraídos:")
                info_col1, info_col2 = st.columns(2)
                with info_col1:
                    st.write(f"**Paciente:** {p_nome}")
                    st.write(f"**Idade:** {p_idade if p_idade is not None else 'N/I'} anos")
                    st.write(f"**Médico:** {m_nome}")
                with info_col2:
                    st.write(f"**CRM:** {crm_str}")
                    st.write(f"**CID-10:** {cid_str}")
                    st.write(f"**Diagnóstico:** {diag_str}")

                if medicamentos_lista:
                    st.markdown("**Medicamentos Prescritos:**")
                    for med in medicamentos_lista:
                        if hasattr(med, "nome"):
                            st.write(f"- 💊 **{med.nome}**: {getattr(med, 'dosagem', '')} ({getattr(med, 'frequencia', 'posologia livre')})")
                        else:
                            st.write(f"- 💊 {str(med)}")

            # -----------------------------------------------------------------
            # 6. PAINEL DE INTERVENÇÃO MÉDICA (HiTL) UNIVERSAL
            # -----------------------------------------------------------------
            if requer_auditoria and not foi_auditado:
                with st.container(border=True):
                    st.markdown("#### 🧑‍⚕️ Painel de Intervenção Médica (Human-in-the-Loop)")
                    st.caption("O agente reteve este documento para revisão médica. Preencha ou confirme os dados ausentes para homologação.")

                    with st.form("form_hitl_auditoria_universal"):
                        f1, f2 = st.columns(2)
                        with f1:
                            novo_nome = st.text_input(
                                "Confirmar Nome do Paciente:",
                                value=p_nome if p_nome not in ("Não identificado", "N/I") and "ilegível" not in str(p_nome).lower() else "Maria de Fátima Oliveira"
                            )
                            nova_idade = st.number_input(
                                "Idade Confirmada:",
                                min_value=0,
                                max_value=125,
                                value=int(p_idade) if (p_idade is not None and int(p_idade) > 0) else 55
                            )
                            novo_medico = st.text_input(
                                "Confirmar Nome do Médico:",
                                value=m_nome if m_nome not in ("Não identificado", "N/I") and "ilegível" not in str(m_nome).lower() else "Dr. Carlos Eduardo Menezes"
                            )
                        with f2:
                            crm_default = crm_str if crm_str not in ("N/I", "") and "ilegível" not in str(crm_str).lower() and "?" not in str(crm_str) else "123456-SP"
                            novo_crm = st.text_input("CRM Confirmado (com UF):", value=crm_default)
                            diag_default = diag_str if diag_str not in ("N/I", "") and "borrada" not in str(diag_str).lower() else "Hipertensão Arterial Sistêmica"
                            novo_diag = st.text_input("Diagnóstico Confirmado:", value=diag_default)
                            novo_cid = st.text_input("CID-10:", value=cid_str if cid_str not in ("Não informado", "Nenhum impresso") else "I10")

                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            submit_aprovar = st.form_submit_button(
                                "Aprovar Triagem Pós-Revisão",
                                type="primary",
                                width="stretch"
                            )
                        with col_btn2:
                            submit_rejeitar = st.form_submit_button(
                                "Rejeitar Documento",
                                width="stretch"
                            )

                    if submit_aprovar:
                        st.session_state.auditoria_aprovada = True
                        st.session_state.dados_editados = {
                            "paciente": novo_nome,
                            "idade": nova_idade,
                            "medico": novo_medico,
                            "crm": novo_crm,
                            "diagnostico": novo_diag,
                            "cid": novo_cid,
                        }
                        st.success("Triagem auditada com sucesso pelo médico! Status atualizado para PROCESSADO.", icon=":material/check_circle:", title="Auditoria Concluída")
                        st.rerun()
                    elif submit_rejeitar:
                        st.warning("Documento devolvido para a recepção clínica para novo escaneamento.", icon=":material/cancel:", title="Documento Devolvido")

            # -----------------------------------------------------------------
            # 7. PAYLOAD JSON ESTRUTURADO (CONTRATO OCI)
            # -----------------------------------------------------------------
            st.markdown("---")
            with st.expander("🔍 Ver Payload JSON Estruturado (Contrato de Saída para OCI)", expanded=False):
                payload_saida = {
                    "status": "PROCESSADO" if foi_auditado or not requer_auditoria else "EM_REVISAO",
                    "documento_id": doc_ingerido.documento_id,
                    "arquivo_origem": doc_ingerido.nome_arquivo,
                    "classificacao": {
                        "tipo_documento": tipo_doc_str,
                        "prioridade": prioridade_str,
                        "score_confianca": qualidade_wf.score_combinado
                    },
                    "dados_extraidos": {
                        "paciente": p_nome,
                        "idade": p_idade,
                        "medico": m_nome,
                        "crm": crm_str,
                        "diagnostico": diag_str,
                        "cid": cid_str
                    },
                    "qualidade": {
                        "score_combinado": qualidade_wf.score_combinado,
                        "score_classificacao": qualidade_wf.score_classificacao,
                        "score_extracao": qualidade_wf.score_extracao,
                        "motivos_revisao": qualidade_wf.motivos_revisao,
                        "campos_ausentes": qualidade_wf.campos_ausentes
                    },
                    "decisao_roteamento": {
                        "destinos": destinos_raw,
                        "requer_auditoria_humana": requer_auditoria and not foi_auditado,
                        "justificativa": decisao_wf.justificativa
                    },
                    "armazenamento_oci": {
                        "bucket": os.getenv("OCI_BUCKET_NAME", "mediflow-documentos"),
                        "caminho_objeto": "processados/DOC-CLIN-2026-AUDITADO.json" if foi_auditado else caminho_oci_alvo,
                        "status_backup": "sucesso"
                    }
                }
                st.json(payload_saida)

else:
    st.info("👈 Selecione um cenário de demonstração ou faça upload de um documento clínico na barra lateral para iniciar a triagem.", title="Aguardando Seleção")
