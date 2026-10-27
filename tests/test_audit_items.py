"""
Suíte de Testes dos 6 Itens de Auditoria Técnica — MediFlow.

Item 1: Urgência INDETERMINADO forçando revisão humana (Decisão A5 / Regra R2).
Item 2: Tipo de documento fora dos previstos exigindo revisão humana.
Item 3: Exceção de diagnóstico ausente restrita a laudos laboratoriais.
Item 4: PDF multipágina híbrido (com página sem texto nativo) sinalizando requer_ocr=True.
Item 5: Preservação de qualidade e decisão calculadas em ERRO_PERSISTENCIA.
Item 6: Rejeição prévia de arquivo vazio (0B), TXT sem conteúdo e falsas imagens.
"""
import pytest
from src.schemas import (
    TriagemMediFlow,
    Destino,
    CodigoErro,
    StatusTriagem,
    TipoDocumento,
    Urgencia,
)
from src.ingestion.loader import (
    DocumentLoader,
    IngestaoError,
    DocumentoCorrompidoError,
)
try:
    import pymupdf as fitz
except ImportError:
    import fitz


# ==============================================================================
# ITEM 1: Urgência INDETERMINADO deve forçar revisão humana (A5 / R2)
# ==============================================================================
def test_item1_urgencia_indeterminada_deve_exigir_revisao():
    """Mesmo com score 0.95 e dados completos, urgencia=INDETERMINADO deve gerar EM_REVISAO."""
    payload = {
        "documento_id": "DOC-TEST-A5",
        "classificacao": {
            "tipo_documento": "LAUDO_EXAME_LABORATORIAL",
            "nivel_prioridade": "ROTINA",
            "score_classificacao": 0.95
        },
        "dados_extraidos": {
            "paciente": {"nome": "Maria Silva", "idade": 45},
            "medico": {"nome": "Dr. Carlos", "crm": {"numero": "123456", "uf": "SP"}},
            "diagnostico": "Exame de rotina",
            "urgencia": "INDETERMINADO",
            "score_confianca_extracao": 0.95
        }
    }
    triagem = TriagemMediFlow.model_validate(payload)
    assert triagem.status == StatusTriagem.EM_REVISAO
    assert triagem.decisao_roteamento.requer_auditoria_humana is True
    assert Destino.FILA_REVISAO_HUMANA in triagem.decisao_roteamento.destinos
    assert Destino.PRONTUARIO_ELETRONICO not in triagem.decisao_roteamento.destinos


# ==============================================================================
# ITEM 2: Tipo de documento fora dos previstos deve exigir revisão humana
# ==============================================================================
def test_item2_tipo_invalido_deve_exigir_revisao():
    """Tipo não previsto na taxonomia oficial não pode ir para o prontuário."""
    payload = {
        "documento_id": "DOC-TEST-TIPO",
        "classificacao": {
            "tipo_documento": "TIPO_INVALIDO",
            "nivel_prioridade": "ROTINA",
            "score_classificacao": 0.95
        },
        "dados_extraidos": {
            "paciente": {"nome": "Maria Silva", "idade": 45},
            "medico": {"nome": "Dr. Carlos", "crm": {"numero": "123456", "uf": "SP"}},
            "diagnostico": "Consulta",
            "urgencia": "NAO",
            "score_confianca_extracao": 0.95
        }
    }
    triagem = TriagemMediFlow.model_validate(payload)
    assert triagem.status == StatusTriagem.EM_REVISAO
    assert triagem.decisao_roteamento.requer_auditoria_humana is True
    assert triagem.decisao_roteamento.destinos == [Destino.FILA_REVISAO_HUMANA]


# ==============================================================================
# ITEM 3: Exceção de diagnóstico ausente é restrita a Laudos Laboratoriais
# ==============================================================================
def test_item3_receita_e_guia_sem_diagnostico_exigem_revisao():
    """Receitas ou Guias sem diagnóstico não podem ser liberadas por conterem exames na lista."""
    # Cenário A: Receita Médica com exames listados, mas sem diagnóstico
    payload_receita = {
        "documento_id": "DOC-TEST-REC",
        "classificacao": {
            "tipo_documento": "RECEITUARIO_MEDICO",
            "nivel_prioridade": "ROTINA",
            "score_classificacao": 0.95
        },
        "dados_extraidos": {
            "paciente": {"nome": "Maria Silva", "idade": 45},
            "medico": {"nome": "Dr. Carlos", "crm": {"numero": "123456", "uf": "SP"}},
            "diagnostico": None,
            "exames": ["Glicemia em jejum"],
            "urgencia": "NAO",
            "score_confianca_extracao": 0.95
        }
    }
    triagem_rec = TriagemMediFlow.model_validate(payload_receita)
    assert "diagnostico" in triagem_rec.qualidade.campos_ausentes
    assert triagem_rec.decisao_roteamento.requer_auditoria_humana is True
    assert triagem_rec.decisao_roteamento.destinos == [Destino.FILA_REVISAO_HUMANA]

    # Cenário B: Guia com exames listados, mas sem diagnóstico
    payload_guia = {
        "documento_id": "DOC-TEST-GUIA",
        "classificacao": {
            "tipo_documento": "GUIA_PROCEDIMENTO",
            "nivel_prioridade": "ROTINA",
            "score_classificacao": 0.95
        },
        "dados_extraidos": {
            "paciente": {"nome": "Maria Silva", "idade": 45},
            "medico": {"nome": "Dr. Carlos", "crm": {"numero": "123456", "uf": "SP"}},
            "diagnostico": None,
            "exames": ["Ressonância Magnética"],
            "urgencia": "NAO",
            "score_confianca_extracao": 0.95
        }
    }
    triagem_guia = TriagemMediFlow.model_validate(payload_guia)
    assert "diagnostico" in triagem_guia.qualidade.campos_ausentes
    assert triagem_guia.decisao_roteamento.requer_auditoria_humana is True

    # Cenário C: Laudo Laboratorial com exame pode ter diagnóstico dispensado
    payload_lab = {
        "documento_id": "DOC-TEST-LAB",
        "classificacao": {
            "tipo_documento": "LAUDO_EXAME_LABORATORIAL",
            "nivel_prioridade": "ROTINA",
            "score_classificacao": 0.95
        },
        "dados_extraidos": {
            "paciente": {"nome": "Maria Silva", "idade": 45},
            "medico": {"nome": "Dr. Carlos", "crm": {"numero": "123456", "uf": "SP"}},
            "diagnostico": None,
            "exames": ["Hemograma Completo"],
            "urgencia": "NAO",
            "score_confianca_extracao": 0.95
        }
    }
    triagem_lab = TriagemMediFlow.model_validate(payload_lab)
    assert "diagnostico" not in triagem_lab.qualidade.campos_ausentes
    assert triagem_lab.decisao_roteamento.requer_auditoria_humana is False
    assert triagem_lab.status == StatusTriagem.PROCESSADO


# ==============================================================================
# ITEM 4: PDF multipágina híbrido (com página sem texto nativo) requer OCR
# ==============================================================================
def test_item4_pdf_hibrido_com_pagina_digitalizada_requer_ocr():
    """PDF de 2 páginas onde uma possui texto e a outra é digitalizada deve sinalizar requer_ocr=True."""
    doc_fitz = fitz.open()
    p1 = doc_fitz.new_page()
    p1.insert_text((50, 50), "Texto nativo da pagina 1.")
    p2 = doc_fitz.new_page()  # Página 2 sem texto nativo (escaneada/imagem)
    pdf_bytes = doc_fitz.tobytes()
    doc_fitz.close()

    doc = DocumentLoader.carregar_bytes(pdf_bytes, nome_arquivo="hibrido.pdf")
    assert doc.total_paginas == 2
    assert doc.metadados["paginas_sem_texto"] == 1
    assert doc.requer_ocr is True


# ==============================================================================
# ITEM 5: Preservação de qualidade e decisão em ERRO_PERSISTENCIA
# ==============================================================================
def test_item5_erro_persistencia_preserva_qualidade_e_decisao():
    """Quando o status é ERRO_PERSISTENCIA, qualidade e decisão devem ser mantidas e erro identificado."""
    payload = {
        "status": "ERRO_PERSISTENCIA",
        "documento_id": "DOC-TEST-OCI-FAIL",
        "classificacao": {
            "tipo_documento": "RECEITUARIO_MEDICO",
            "nivel_prioridade": "ROTINA",
            "score_classificacao": 0.90
        },
        "dados_extraidos": {
            "paciente": {"nome": "Maria Silva", "idade": 45},
            "medico": {"nome": "Dr. Carlos", "crm": {"numero": "123456", "uf": "SP"}},
            "diagnostico": "Hipertensão",
            "urgencia": "NAO",
            "score_confianca_extracao": 0.90
        }
    }
    triagem = TriagemMediFlow.model_validate(payload)
    assert triagem.status == StatusTriagem.ERRO_PERSISTENCIA
    assert triagem.qualidade is not None
    assert triagem.decisao_roteamento is not None
    assert triagem.decisao_roteamento.destino_principal == Destino.FARMACIA_HOSPITALAR
    assert triagem.erro is not None
    assert triagem.erro.codigo == CodigoErro.ERRO_PERSISTENCIA


# ==============================================================================
# ITEM 6: Validação prévia de arquivos vazios, TXT sem conteúdo e falsas imagens
# ==============================================================================
def test_item6_rejeicao_arquivo_vazio():
    """Arquivo de 0 bytes deve ser rejeitado antecipadamente."""
    with pytest.raises(IngestaoError) as exc:
        DocumentLoader.carregar_bytes(b"", nome_arquivo="vazio.pdf")
    assert "VAZIO" in exc.value.codigo


def test_item6_rejeicao_txt_somente_espacos():
    """Arquivo TXT sem caracteres visíveis válidos deve ser rejeitado."""
    with pytest.raises(IngestaoError) as exc:
        DocumentLoader.carregar_bytes(b"   \n\t  \r\n", nome_arquivo="espacos.txt")
    assert "VAZIO" in exc.value.codigo


def test_item6_rejeicao_texto_renomeado_para_imagem():
    """Texto comum com extensão de imagem (.png, .jpg, .webp) deve ser barrado por assinatura inválida."""
    texto_fake_png = b"Este e um texto normal em ascii, nao e imagem png."
    with pytest.raises(DocumentoCorrompidoError) as exc:
        DocumentLoader.carregar_bytes(texto_fake_png, nome_arquivo="falso.png")
    assert "CORROMPIDO" in exc.value.codigo or "INVALIDA" in exc.value.codigo
