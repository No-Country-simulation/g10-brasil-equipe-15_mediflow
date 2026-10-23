"""
MediFlow — Interface de Demonstração e Auditoria Clínica (Streamlit MVP).
Equipe 15 · Hackathon ONE G10 (Oracle & Alura).
Permite ingestão de arquivos (PDF/Imagem/TXT) e visualização em tempo real da triagem clínica.
"""
import sys
from pathlib import Path

# Garante que a raiz do projeto esteja no sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
from src.ingestion import DocumentLoader, IngestaoError

# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="MediFlow — Triagem Clínica Autônoma",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização CSS customizada para visual HealthTech moderno
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0px;
    }
    .sub-header {
        font-size: 1rem;
        color: #4B5563;
        margin-bottom: 20px;
    }
    .card-urgente {
        background-color: #FEF2F2;
        border-left: 5px solid #EF4444;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 15px;
    }
    .card-revisao {
        background-color: #FFFBEB;
        border-left: 5px solid #F59E0B;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 15px;
    }
    .card-rotina {
        background-color: #F0FDF4;
        border-left: 5px solid #10B981;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 15px;
    }
    .badge-alerta {
        background-color: #DC2626;
        color: white;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: bold;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# CENÁRIOS DEMO PRÉ-CONFIGURADOS (DO EDITAL E FIXTURES)
# ==============================================================================
CENARIOS_DEMO = {
    "Cenário 1: Rotina (RX de Tórax Normal)": {
        "arquivo": "01_laudo_rotina.pdf",
        "tipo": "Laudo de Exame de Imagem",
        "especialidade": "Radiologia",
        "prioridade": "Rotina",
        "score": 0.96,
        "paciente": "João Carlos da Silva",
        "idade": 42,
        "medico": "Dr. Roberto Mendes (CRM: 112345-SP)",
        "diagnostico": "Radiografia de tórax dentro dos limites da normalidade.",
        "destino": "Prontuário Eletrônico do Paciente",
        "requer_auditoria": False,
        "justificativa": "Laudo admissional sem alterações clínicas significativas."
    },
    "Cenário 2: Urgência Crítica (Angiotomografia - TEP Agudo)": {
        "arquivo": "02_laudo_urgencia_tep.pdf",
        "tipo": "Laudo de Exame de Imagem",
        "especialidade": "Radiologia / Pneumologia",
        "prioridade": "Urgente",
        "score": 0.99,
        "paciente": "Maria Eduarda Santos",
        "idade": 61,
        "medico": "Dra. Camila Alencar (CRM: 98765-SP)",
        "diagnostico": "Tromboembolismo Pulmonar Agudo Massivo (CID-10: I26.9)",
        "destino": "Fila de Emergência Médica",
        "requer_auditoria": True,
        "alerta": "🚨 ALERTA URGENTE: Tromboembolismo Pulmonar Agudo detectado. Encaminhar para UTI/Hemodinâmica.",
        "justificativa": "Achado crítico de alta gravidade (oclusão vascular e sobrecarga de câmaras direitas)."
    },
    "Cenário 3: Ambiguidade / Rasura (Receituário - Human-in-the-Loop)": {
        "arquivo": "03_receituario_ambiguo.pdf",
        "tipo": "Receituário Médico",
        "especialidade": "Clínica Médica / Farmácia",
        "prioridade": "Ambiguidade / Revisão",
        "score": 0.65,
        "paciente": "Maria de Fátima Oliveira [Nome parcialmente ilegível]",
        "idade": 55,
        "medico": "Dr. [Assinatura ilegível] (CRM: 123...?-SP [Rasurado])",
        "diagnostico": "Prescrição de anti-hipertensivo com dosagem borrada",
        "destino": "Fila de Revisão Humana (Auditoria Médica)",
        "requer_auditoria": True,
        "justificativa": "Score combinado (0.65) abaixo do limiar (0.85), carimbo do CRM rasurado e dosagem ambígua."
    }
}

# ==============================================================================
# BARRA LATERAL (CONTROLES E INGESTÃO)
# ==============================================================================
with st.sidebar:
    st.image("https://img.shields.io/badge/MediFlow-Equipe%2015-blue?style=for-the-badge", use_container_width=True)
    st.markdown("### ⚙️ Painel de Controle")
    
    modo_entrada = st.radio(
        "Origem do Documento:",
        ["🧪 Cenários Oficiais (Demo)", "📤 Upload de Arquivo Real"]
    )
    
    doc_ingerido = None
    dados_mock = None

    if modo_entrada == "🧪 Cenários Oficiais (Demo)":
        cenario_escolhido = st.selectbox(
            "Selecione um caso clínico:",
            list(CENARIOS_DEMO.keys())
        )
        dados_mock = CENARIOS_DEMO[cenario_escolhido]
        caminho_pdf = ROOT_DIR / "data" / "samples" / dados_mock["arquivo"]
        
        if caminho_pdf.exists():
            doc_ingerido = DocumentLoader.carregar_arquivo(caminho_pdf)
        else:
            st.warning("Arquivo PDF de teste não encontrado localmente.")
            
    else:
        uploaded_file = st.file_uploader(
            "Arraste ou selecione um laudo/receita:",
            type=["pdf", "png", "jpg", "jpeg", "txt"],
            help="Formatos aceitos: PDF, TXT ou Imagens (Máx: 20MB)"
        )
        
        if uploaded_file is not None:
            try:
                bytes_data = uploaded_file.read()
                doc_ingerido = DocumentLoader.carregar_bytes(
                    conteudo_bytes=bytes_data,
                    nome_arquivo=uploaded_file.name
                )
                st.success(f"Arquivo lido com sucesso! ({doc_ingerido.tamanho_bytes / 1024:.1f} KB)")
            except IngestaoError as e:
                st.error(f"Erro de Ingestão: {e.codigo} — {e.mensagem}")
            except Exception as e:
                st.error(f"Erro inesperado: {str(e)}")

    st.markdown("---")
    st.markdown("**Hackathon ONE G10 — Oracle & Alura**")
    st.caption("Agente Autônomo para Triagem, Extração e Roteamento de Documentos Clínicos.")

# ==============================================================================
# CABEÇALHO PRINCIPAL
# ==============================================================================
col_logo, col_titulo = st.columns([1, 8])
with col_logo:
    st.markdown("<h1 style='font-size: 3rem;'>🏥</h1>", unsafe_allow_html=True)
with col_titulo:
    st.markdown("<div class='main-header'>MediFlow — Triagem Documental Inteligente</div>", unsafe_allow_html=True)
    st.markdown("<div class='sub-header'>Pipeline com Ingestão PyMuPDF · Validação Pydantic v2 · Roteamento Hospitalar OCI</div>", unsafe_allow_html=True)

st.markdown("---")

# ==============================================================================
# CORPO PRINCIPAL (VISÃO LADO A LADO)
# ==============================================================================
if doc_ingerido is not None:
    col_esquerda, col_direita = st.columns([1, 1], gap="medium")

    # -------------------------------------------------------------------------
    # COLUNA ESQUERDA: DOCUMENTO ORIGINAL E METADADOS DA INGESTÃO
    # -------------------------------------------------------------------------
    with col_esquerda:
        st.subheader("📄 Documento Ingerido")
        
        # Cards de métricas rápidas da ingestão
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Formato", doc_ingerido.formato)
        m2.metric("Páginas", doc_ingerido.total_paginas)
        m3.metric("Tamanho", f"{doc_ingerido.tamanho_bytes / 1024:.1f} KB")
        m4.metric("OCR Visual?", "Sim" if doc_ingerido.requer_ocr else "Não")

        st.caption(f"**Identificador Único:** `{doc_ingerido.documento_id}` | **Arquivo:** `{doc_ingerido.nome_arquivo}`")
        
        # Exibição do texto extraído pelo leitor
        st.markdown("**Texto Extraído pelo PyMuPDF:**")
        st.text_area(
            label="Conteúdo Bruto",
            value=doc_ingerido.conteudo_texto if doc_ingerido.conteudo_texto else "[Mídia em Imagem/Scaneada — requer visão multimodal]",
            height=380,
            disabled=True,
            label_visibility="collapsed"
        )

    # -------------------------------------------------------------------------
    # COLUNA DIREITA: RESULTADO DA TRIAGEM CLÍNICA & DECISÃO
    # -------------------------------------------------------------------------
    with col_direita:
        st.subheader("⚖️ Decisão do Agente & Roteamento")
        
        # Se temos dados pré-formatados do cenário demo
        if dados_mock:
            prioridade = dados_mock["prioridade"]
            score = dados_mock["score"]
            
            # Card de Status Dinâmico por Gravidade
            if prioridade == "Urgente":
                st.markdown(f"""
                <div class='card-urgente'>
                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                        <h3 style='margin: 0; color: #DC2626;'>🚨 CASO CRÍTICO / URGÊNCIA</h3>
                        <span class='badge-alerta'>ALERTA PLANTÃO</span>
                    </div>
                    <p style='margin-top: 8px; font-weight: bold;'>Destino: {dados_mock['destino']}</p>
                    <p style='margin: 0;'><b>Justificativa:</b> {dados_mock['justificativa']}</p>
                </div>
                """, unsafe_allow_html=True)
                if "alerta" in dados_mock:
                    st.error(dados_mock["alerta"])
                    
            elif "Revisão" in prioridade or score < 0.85:
                st.markdown(f"""
                <div class='card-revisao'>
                    <h3 style='margin: 0; color: #D97706;'>🧑‍⚕️ REQUER REVISÃO HUMANA (Human-in-the-Loop)</h3>
                    <p style='margin-top: 8px; font-weight: bold;'>Destino: {dados_mock['destino']}</p>
                    <p style='margin: 0;'><b>Motivo da Retenção:</b> {dados_mock['justificativa']}</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class='card-rotina'>
                    <h3 style='margin: 0; color: #059669;'>🟢 PROCESSAMENTO AUTÔNOMO (ROTINA)</h3>
                    <p style='margin-top: 8px; font-weight: bold;'>Destino: {dados_mock['destino']}</p>
                    <p style='margin: 0;'><b>Justificativa:</b> {dados_mock['justificativa']}</p>
                </div>
                """, unsafe_allow_html=True)

            # Informações Clínicas Extraídas
            st.markdown("#### 📋 Dados Clínicos Extraídos:")
            info_col1, info_col2 = st.columns(2)
            with info_col1:
                st.write(f"**Paciente:** {dados_mock['paciente']}")
                st.write(f"**Idade:** {dados_mock['idade']} anos")
                st.write(f"**Médico Solicitante:** {dados_mock['medico']}")
            with info_col2:
                st.write(f"**Especialidade:** {dados_mock['especialidade']}")
                st.write(f"**Score de Confiança:** `{score:.2f}` ({'Aprovado' if score >= 0.85 else 'Baixa Confiança'})")
                st.write(f"**Diagnóstico / Achado:** {dados_mock['diagnostico']}")

            # Interatividade Human-in-the-Loop para o Médico Auditor
            if dados_mock["requer_auditoria"]:
                st.markdown("---")
                st.markdown("#### 🧑‍⚕️ Painel do Auditor Clínico (Dr. Marcos):")
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("✅ Aprovar Extração e Despachar", use_container_width=True, type="primary"):
                        st.success(f"Laudo `{doc_ingerido.documento_id}` aprovado pelo auditor! Enviado para persitência OCI.")
                with col_btn2:
                    if st.button("❌ Rejeitar / Solicitar Novo Upload", use_container_width=True):
                        st.warning("Documento devolvido para a recepção do hospital.")

        else:
            # Caso de upload real de arquivo novo
            st.info("Arquivo recebido com sucesso na Ingestão! O texto bruto está pronto para envio à API do Gemini para classificação automática.")
            st.markdown(f"""
            - **Documento ID:** `{doc_ingerido.documento_id}`
            - **Status:** `RECEBIDO_EM_FILA`
            - **Caracteres Extraídos:** {len(doc_ingerido.conteudo_texto)}
            """)

    # -------------------------------------------------------------------------
    # ABA INFERIOR: PAYLOAD JSON ESTRUTURADO (PRONTO PARA ORACLE CLOUD)
    # -------------------------------------------------------------------------
    st.markdown("---")
    with st.expander("🔍 Ver Payload JSON Estruturado (Contrato de Saída para OCI)", expanded=False):
        payload_exemplo = {
            "status": "PROCESSADO" if (dados_mock and not dados_mock.get("requer_auditoria")) else "EM_REVISAO",
            "documento_id": doc_ingerido.documento_id,
            "arquivo_origem": doc_ingerido.nome_arquivo,
            "classificacao": {
                "tipo_documento": dados_mock["tipo"] if dados_mock else "DOCUMENTO_CLINICO",
                "prioridade": dados_mock["prioridade"] if dados_mock else "ROTINA",
                "score_confianca": dados_mock["score"] if dados_mock else 0.95
            },
            "dados_extraidos": {
                "paciente": dados_mock["paciente"] if dados_mock else "Extração via LLM",
                "medico": dados_mock["medico"] if dados_mock else "Extração via LLM",
                "diagnostico": dados_mock["diagnostico"] if dados_mock else "Extração via LLM"
            },
            "armazenamento_oci": {
                "bucket": "mediflow-documentos-clinicos",
                "caminho_objeto": f"processados/{doc_ingerido.documento_id}.json",
                "status_backup": "sucesso"
            }
        }
        st.json(payload_exemplo)

else:
    st.info("👈 Selecione um cenário de demonstração ou faça upload de um documento clínico na barra lateral para iniciar a triagem.")
