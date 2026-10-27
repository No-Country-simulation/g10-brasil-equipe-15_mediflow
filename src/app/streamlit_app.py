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

from src.ingestion import DocumentLoader, IngestaoError
from src.services.gemini_service import GeminiService
from src.workflow.graph import criar_grafo
from src.workflow.state import EntradaWorkflow
from src.schemas import (
    TriagemMediFlow,
    StatusTriagem,
    Destino,
    Classificacao,
    DadosExtraidos,
    Paciente,
    Medico,
    Crm,
    NivelPrioridade,
)

load_dotenv(override=True)

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
    # COLUNA DIREITA: RESULTADO DA TRIAGEM CLÍNICA & DECISÃO
    # -------------------------------------------------------------------------
    with col_direita:
        st.subheader("⚖️ Decisão do Agente & Roteamento", anchor=False)
        
        # ---------------------------------------------------------------------
        # MODO 1: CENÁRIOS DEMO DO EDITAL
        # ---------------------------------------------------------------------
        if dados_mock:
            prioridade = dados_mock["prioridade"]
            score_comb = dados_mock["score_combinado"]
            foi_auditado = st.session_state.auditoria_aprovada
            
            # Card de Status Dinâmico Nativo
            if foi_auditado:
                with st.container(border=True):
                    st.success("🟢 PROCESSAMENTO HOMOLOGADO (PÓS-AUDITORIA MÉDICA)", icon=":material/verified:")
                    st.markdown(f"**Destino:** `Prontuário Eletrônico do Paciente`")
                    st.markdown(f"**Justificativa:** Documento auditado, corrigido e aprovado pelo Médico Auditor (Human-in-the-Loop).")
                    st.caption("📦 Backup OCI: `processados/DOC-CLIN-2026-AUDITADO.json`")
            elif prioridade == "Urgente":
                with st.container(border=True):
                    st.error("🚨 CASO CRÍTICO / URGÊNCIA DETECTADA", icon=":material/emergency:")
                    st.markdown(f"**Destino Hospitalar:** `{dados_mock['destino']}`")
                    st.markdown(f"**Justificativa:** {dados_mock['justificativa']}")
                    st.caption(f"📦 Backup OCI: `{dados_mock['pasta_oci']}`")
                if "alerta" in dados_mock:
                    st.warning(dados_mock["alerta"], icon=":material/notification_important:", title="Alerta Imediato")
                    
            elif "Revisão" in prioridade or score_comb < 0.85:
                with st.container(border=True):
                    st.warning("🧑‍⚕️ REQUER REVISÃO HUMANA (Human-in-the-Loop)", icon=":material/assignment_late:")
                    st.markdown(f"**Destino Hospitalar:** `{dados_mock['destino']}`")
                    st.markdown(f"**Motivo da Retenção:** {dados_mock['justificativa']}")
                    st.caption(f"📦 Backup OCI: `{dados_mock['pasta_oci']}`")
            else:
                with st.container(border=True):
                    st.success("🟢 PROCESSAMENTO AUTÔNOMO APROVADO (ROTINA)", icon=":material/verified:")
                    st.markdown(f"**Destino Hospitalar:** `{dados_mock['destino']}`")
                    st.markdown(f"**Justificativa:** {dados_mock['justificativa']}")
                    st.caption(f"📦 Backup OCI: `{dados_mock['pasta_oci']}`")

            # Avaliação de Qualidade e Scores (Fórmula A3)
            with st.container(border=True):
                st.markdown("#### 📊 Avaliação de Qualidade (Fórmula Determinística A3)")
                sc1, sc2, sc3 = st.columns(3)
                sc1.metric("Score Combinado", f"{score_comb:.2f}", delta="Aprovado (>= 0.85)" if score_comb >= 0.85 else "Retido (< 0.85)", delta_color="normal" if score_comb >= 0.85 else "inverse")
                sc2.metric("Classificação", f"{dados_mock['score_classif']:.2f}")
                sc3.metric("Extração", f"{dados_mock['score_extrac']:.2f}")

            # Informações Clínicas Extraídas
            with st.container(border=True):
                st.markdown("#### 📋 Dados Clínicos Extraídos:")
                info_col1, info_col2 = st.columns(2)
                with info_col1:
                    st.write(f"**Paciente:** {dados_mock['paciente']}")
                    st.write(f"**Idade:** {dados_mock['idade']} anos")
                    st.write(f"**Médico Solicitante:** {dados_mock['medico']}")
                with info_col2:
                    st.write(f"**CRM:** {dados_mock['crm']}")
                    st.write(f"**CID-10:** {dados_mock['cid'] or 'Não informado'}")
                    st.write(f"**Diagnóstico / Achado:** {dados_mock['diagnostico']}")

            # Painel Human-in-the-Loop (HiTL) para casos em revisão
            if dados_mock["requer_auditoria"] and not foi_auditado:
                with st.container(border=True):
                    st.markdown("#### 🧑‍⚕️ Painel de Intervenção Médica (Human-in-the-Loop)")
                    st.caption("Revise os campos ilegíveis ou ambíguos antes de homologar a extração no sistema hospitalar.")
                    
                    with st.form("form_hitl_auditoria"):
                        f1, f2 = st.columns(2)
                        with f1:
                            novo_nome = st.text_input("Confirmar Nome do Paciente:", value="Maria de Fátima Oliveira")
                            nova_idade = st.number_input("Idade Confirmada:", min_value=0, max_value=125, value=55)
                            novo_medico = st.text_input("Confirmar Nome do Médico:", value="Dr. Carlos Eduardo Menezes")
                        with f2:
                            novo_crm = st.text_input("CRM Confirmado (com UF):", value="123456-SP")
                            novo_diag = st.text_input("Diagnóstico Confirmado:", value="Hipertensão Arterial Sistêmica")
                            novo_cid = st.text_input("CID-10:", value="I10")

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
                        st.success("Triagem auditada com sucesso pelo médico! Status atualizado para PROCESSADO.", icon=":material/check_circle:", title="Auditoria Concluída")
                        st.rerun()
                    elif submit_rejeitar:
                        st.warning("Documento devolvido para a recepção clínica para novo escaneamento.", icon=":material/cancel:", title="Documento Devolvido")

        # ---------------------------------------------------------------------
        # MODO 2: UPLOAD REAL COM GOOGLE GEMINI + LANGGRAPH
        # ---------------------------------------------------------------------
        else:
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
                    
                    # Conecta os sinais estruturados do Gemini com o Grafo LangGraph
                    grafo = criar_grafo()
                    entrada_wf = EntradaWorkflow(
                        documento_id=doc_ingerido.documento_id,
                        classificacao=classif,
                        dados_extraidos=extrac,
                        urgencia="SIM" if "URGENTE" in str(getattr(classif, "nivel_prioridade", "")).upper() else "NAO"
                    )
                    estado_wf = grafo.invoke({"entrada": entrada_wf})
                    
                    st.session_state.resultado_ia = {
                        "classificacao": classif,
                        "extracao": extrac,
                        "qualidade_wf": estado_wf.get("qualidade"),
                        "decisao_wf": estado_wf.get("decisao"),
                        "chave_ativa": bool(api_key_custom or tem_chave_valida),
                        "simulado": False
                    }

            if usar_fallback_teste:
                st.session_state.resultado_ia = {
                    "simulado": True
                }

            if st.session_state.resultado_ia:
                res = st.session_state.resultado_ia
                if res.get("simulado"):
                    with st.container(border=True):
                        st.success("🟢 PROCESSAMENTO AUTÔNOMO (SIMULAÇÃO LOCAL)", icon=":material/bolt:")
                        st.markdown("**Destino:** `Prontuário Eletrônico do Paciente`")
                        st.markdown("**Justificativa:** Documento clínico analisado com sucesso em modo de demonstração local.")
                else:
                    classif = res["classificacao"]
                    extrac = res["extracao"]
                    qualidade_wf = res.get("qualidade_wf")
                    decisao_wf = res.get("decisao_wf")

                    tipo_doc_str = classif.tipo_documento.value if hasattr(classif.tipo_documento, "value") else str(classif.tipo_documento)
                    prioridade_str = classif.nivel_prioridade.value if hasattr(classif.nivel_prioridade, "value") else str(classif.nivel_prioridade)
                    
                    score_classif_val = getattr(classif, "score_confianca_classificacao", 0.95)
                    score_extrac_val = getattr(qualidade_wf, "score_extracao", getattr(extrac, "score_confianca_extracao", 0.90)) if qualidade_wf else 0.90
                    score_combinado_val = getattr(qualidade_wf, "score_combinado", min(score_classif_val, score_extrac_val)) if qualidade_wf else min(score_classif_val, score_extrac_val)
                    
                    destinos_wf = getattr(decisao_wf, "destinos", ["PRONTUARIO_ELETRONICO"]) if decisao_wf else ["PRONTUARIO_ELETRONICO"]
                    destinos_str = ", ".join([d.value if hasattr(d, "value") else str(d) for d in destinos_wf])
                    justificativa_wf = getattr(decisao_wf, "justificativa", "Triagem clínica finalizada.") if decisao_wf else "Triagem clínica finalizada."
                    status_wf = getattr(decisao_wf, "status", "PROCESSADO") if decisao_wf else "PROCESSADO"

                    if not res.get("chave_ativa"):
                        st.warning(
                            "Chave GEMINI_API_KEY não configurada ou inválida. O serviço operou com o fail-safe resiliente (Seção 12 E.F.), direcionando para revisão humana.",
                            title="Aviso de Segurança Fail-Safe"
                        )

                    # Card de Decisão LangGraph
                    with st.container(border=True):
                        if "URGENTE" in prioridade_str.upper() or "URGENCIA" in destinos_str.upper():
                            st.error("🚨 ACHADO CRÍTICO / URGÊNCIA CLÍNICA", icon=":material/emergency:")
                            st.markdown(f"**Destino:** `{destinos_str}`")
                            st.markdown(f"**Justificativa:** {justificativa_wf}")
                            st.caption("📦 Pasta OCI: `processados/urgentes/`")
                        elif status_wf == "EM_REVISAO" or score_combinado_val < 0.85 or "NAO_IDENTIFICAD" in tipo_doc_str:
                            st.warning("🧑‍⚕️ REQUER REVISÃO HUMANA (Auditoria Médica)", icon=":material/assignment_late:")
                            st.markdown(f"**Destino:** `{destinos_str}`")
                            st.markdown(f"**Motivo da Retenção:** {justificativa_wf}")
                            st.caption("📦 Pasta OCI: `auditoria/`")
                        else:
                            st.success("🟢 PROCESSAMENTO AUTÔNOMO APROVADO", icon=":material/verified:")
                            st.markdown(f"**Destino:** `{destinos_str}`")
                            st.markdown(f"**Justificativa:** {justificativa_wf}")
                            st.caption("📦 Pasta OCI: `processados/`")

                    # Breakdown de Scores A3
                    with st.container(border=True):
                        st.markdown("#### 📊 Avaliação de Qualidade (Fórmula Determinística A3)")
                        q1, q2, q3 = st.columns(3)
                        q1.metric("Score Combinado", f"{score_combinado_val:.2f}", delta="Aprovado (>= 0.85)" if score_combinado_val >= 0.85 else "Retido (< 0.85)", delta_color="normal" if score_combinado_val >= 0.85 else "inverse")
                        q2.metric("Classificação", f"{score_classif_val:.2f}")
                        q3.metric("Extração", f"{score_extrac_val:.2f}")

                    # Entidades Clínicas Extraídas
                    with st.container(border=True):
                        st.markdown("#### 📋 Entidades Extraídas:")
                        col_e1, col_e2 = st.columns(2)
                        
                        paciente_obj = getattr(extrac, "paciente", None)
                        p_nome = getattr(paciente_obj, "nome", None) or "Não identificado"
                        p_idade = getattr(paciente_obj, "idade", None)
                        
                        medico_obj = getattr(extrac, "medico_solicitante", getattr(extrac, "medico", None))
                        m_nome = getattr(medico_obj, "nome", None) or "Não identificado"
                        
                        # Extrai CRM limpo
                        crm_raw = getattr(medico_obj, "crm", None)
                        if hasattr(crm_raw, "numero") and hasattr(crm_raw, "uf"):
                            crm_num = re.sub(r"(?i)^crm[\s\:\/\.\-]*", "", str(crm_raw.numero or "")).strip()
                            crm_uf = str(crm_raw.uf or "").strip()
                            crm_str = f"{crm_num}-{crm_uf}" if crm_num and crm_uf else (crm_num or crm_uf or "N/I")
                        else:
                            crm_str = re.sub(r"(?i)^crm[\s\:\/\.\-]*", "", str(crm_raw or "")).strip() or "N/I"
                        
                        diag_str = getattr(extrac, "diagnostico_principal", getattr(extrac, "diagnostico", None)) or "N/I"
                        cid_str = getattr(extrac, "cid_extraido", getattr(extrac, "cid", None)) or "Nenhum impresso"

                        with col_e1:
                            st.write(f"**Paciente:** {p_nome}")
                            st.write(f"**Idade:** {p_idade if p_idade is not None else 'N/I'} anos")
                            st.write(f"**Médico:** {m_nome}")
                        with col_e2:
                            st.write(f"**CRM:** {crm_str}")
                            st.write(f"**CID-10:** {cid_str}")
                            st.write(f"**Diagnóstico:** {diag_str}")

                        medicamentos_lista = getattr(extrac, "medicamentos", [])
                        if medicamentos_lista:
                            st.markdown("**Medicamentos Prescritos:**")
                            for med in medicamentos_lista:
                                if hasattr(med, "nome"):
                                    st.write(f"- 💊 **{med.nome}**: {getattr(med, 'dosagem', '')} ({getattr(med, 'frequencia', 'posologia livre')})")
                                else:
                                    st.write(f"- 💊 {str(med)}")

    # -------------------------------------------------------------------------
    # ABA INFERIOR: PAYLOAD JSON ESTRUTURADO (CONTRATO DE DADOS OCI)
    # -------------------------------------------------------------------------
    st.markdown("---")
    with st.expander("🔍 Ver Payload JSON Estruturado (Contrato de Saída para OCI)", expanded=False):
        payload_saida = {
            "status": "PROCESSADO" if (dados_mock and not dados_mock.get("requer_auditoria")) else "EM_REVISAO",
            "documento_id": doc_ingerido.documento_id,
            "arquivo_origem": doc_ingerido.nome_arquivo,
            "classificacao": {
                "tipo_documento": dados_mock["tipo"] if dados_mock else tipo_doc_str,
                "prioridade": dados_mock["prioridade"] if dados_mock else prioridade_str,
                "score_confianca": dados_mock["score_combinado"] if dados_mock else score_combinado_val
            },
            "dados_extraidos": {
                "paciente": dados_mock["paciente"] if dados_mock else p_nome,
                "medico": dados_mock["medico"] if dados_mock else m_nome,
                "crm": dados_mock["crm"] if dados_mock else crm_str,
                "diagnostico": dados_mock["diagnostico"] if dados_mock else diag_str
            },
            "armazenamento_oci": {
                "bucket": os.getenv("OCI_BUCKET_NAME", "mediflow-documentos"),
                "caminho_objeto": dados_mock["pasta_oci"] if dados_mock else f"processados/{doc_ingerido.documento_id}.json",
                "status_backup": "sucesso"
            }
        }
        st.json(payload_saida)

else:
    st.info("👈 Selecione um cenário de demonstração ou faça upload de um documento clínico na barra lateral para iniciar a triagem.", title="Aguardando Seleção")
