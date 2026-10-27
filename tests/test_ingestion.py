"""
Testes unitários para o módulo de ingestão blindado de documentos (DocumentLoader).
Valida leitura de PDFs, encoding Latin-1/UTF-8, limite de tamanho, senha e integridade.
"""
from pathlib import Path
import pytest
from src.ingestion import (
    DocumentLoader,
    DocumentoIngerido,
    TamanhoExcedidoError,
    DocumentoProtegidoError,
    DocumentoCorrompidoError,
)

try:
    import pymupdf as fitz
except ImportError:
    import fitz

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "data" / "samples"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_carregar_pdf_rotina():
    """Valida a leitura do PDF do Cenário 1 (Rotina - RX de Tórax)"""
    pdf_path = SAMPLES_DIR / "01_laudo_rotina.pdf"
    assert pdf_path.exists(), "PDF de teste deve existir em data/samples/"

    doc = DocumentLoader.carregar_arquivo(pdf_path)

    assert isinstance(doc, DocumentoIngerido)
    assert doc.formato == "PDF"
    assert doc.total_paginas == 1
    assert doc.requer_ocr is False
    assert "João Carlos da Silva" in doc.conteudo_texto
    assert "RADIOGRAFIA DE TÓRAX" in doc.conteudo_texto
    assert doc.metadados["total_caracteres"] > 100


def test_carregar_pdf_urgencia_tep():
    """Valida a leitura do PDF do Cenário 2 (Urgência Crítica - TEP)"""
    pdf_path = SAMPLES_DIR / "02_laudo_urgencia_tep.pdf"
    doc = DocumentLoader.carregar_arquivo(pdf_path)

    assert doc.formato == "PDF"
    assert "Maria Eduarda Santos" in doc.conteudo_texto
    assert "TROMBOEMBOLISMO PULMONAR" in doc.conteudo_texto
    assert "I26.9" in doc.conteudo_texto
    assert doc.documento_id.startswith("DOC-")


def test_carregar_bytes_pdf():
    """Valida carregamento direto de bytes (upload via Streamlit/FastAPI)"""
    pdf_path = SAMPLES_DIR / "02_laudo_urgencia_tep.pdf"
    with open(pdf_path, "rb") as f:
        bytes_data = f.read()

    doc = DocumentLoader.carregar_bytes(bytes_data, nome_arquivo="upload_urgencia.pdf")

    assert doc.nome_arquivo == "upload_urgencia.pdf"
    assert doc.formato == "PDF"
    assert doc.tamanho_bytes == len(bytes_data)
    assert "Maria Eduarda Santos" in doc.conteudo_texto


def test_limite_tamanho_excedido():
    """Valida bloqueio de segurança para uploads maiores que 10MB (alinhado a Limite_Tamanho_Acima10MB)"""
    tamanho_excessivo = 11 * 1024 * 1024  # 11MB
    dados_ficticios = b"0" * 100  # não aloca 11MB em ram, testa a validação lógica

    with pytest.raises(TamanhoExcedidoError) as exc_info:
        DocumentLoader.validar_limite_tamanho(tamanho_excessivo)

    assert exc_info.value.codigo == "ARQUIVO_MAIOR_QUE_LIMITE"


def test_limite_paginas_excedido():
    """Valida bloqueio de segurança para PDFs com mais de 20 páginas (alinhado a Limite_Paginas_21)"""
    doc_fitz = fitz.open()
    for _ in range(21):
        page = doc_fitz.new_page()
        page.insert_text((50, 50), "Página de teste de limite.")
    pdf_bytes = doc_fitz.tobytes()
    doc_fitz.close()

    with pytest.raises(TamanhoExcedidoError) as exc_info:
        DocumentLoader.carregar_bytes(pdf_bytes, nome_arquivo="documento_longo_21paginas.pdf")

    assert exc_info.value.codigo == "ARQUIVO_MAIOR_QUE_LIMITE"
    assert "20 páginas" in exc_info.value.mensagem


def test_tratamento_encoding_latin1():
    """Valida fallback de encoding preservando acentos em laudos brasileiros antigos"""
    texto_original = "PACIENTE: JOSÉ DA CONCEIÇÃO | PRESCRIÇÃO: ANALGÉSICO CARDÍACO"
    bytes_latin1 = texto_original.encode("iso-8859-1")

    doc = DocumentLoader.carregar_bytes(bytes_latin1, nome_arquivo="receita_antiga.txt")

    assert doc.conteudo_texto == texto_original
    assert "CONCEIÇÃO" in doc.conteudo_texto
    assert "CARDÍACO" in doc.conteudo_texto
    assert doc.metadados["encoding_detectado"] == "iso-8859-1"


def test_pdf_protegido_por_senha():
    """Valida detecção graciosa de PDF protegido por senha sem travar a aplicação"""
    # Cria um PDF temporário criptografado em memória
    doc_fitz = fitz.open()
    doc_fitz.new_page()
    pdf_com_senha_bytes = doc_fitz.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256,
        user_pw="senha123",
        owner_pw="master123"
    )
    doc_fitz.close()

    with pytest.raises(DocumentoProtegidoError) as exc_info:
        DocumentLoader.carregar_bytes(pdf_com_senha_bytes, nome_arquivo="exame_protegido.pdf")

    assert exc_info.value.codigo == "PDF_PROTEGIDO"


def test_pdf_corrompido():
    """Valida detecção de arquivo PDF truncado ou corrompido"""
    bytes_corrompidos = b"%PDF-1.4 corrompido e truncado pela metade..."

    with pytest.raises(DocumentoCorrompidoError) as exc_info:
        DocumentLoader.carregar_bytes(bytes_corrompidos, nome_arquivo="exame_corrompido.pdf")

    assert exc_info.value.codigo == "PDF_CORROMPIDO"


def test_carregamento_imagem_multimodal():
    """Valida carregamento de fotos/imagens preservando bytes para o Gemini"""
    bytes_imagem = b"\x89PNG\r\n\x1a\nfake_image_bytes"
    doc = DocumentLoader.carregar_bytes(bytes_imagem, nome_arquivo="foto_receita.png")

    assert doc.formato == "PNG"
    assert doc.requer_ocr is True
    assert doc.conteudo_bytes == bytes_imagem
    assert doc.metadados["tipo"] == "imagem"


def test_laudo_curto_sem_falso_positivo_ocr():
    """Garante que atestados médicos curtos não sejam falsamente marcados como 'precisa de OCR'"""
    texto_curto = "Atesto que o paciente esteve sob cuidados medicos hoje."
    doc_fitz = fitz.open()
    page = doc_fitz.new_page()
    page.insert_text((50, 50), texto_curto)
    pdf_bytes = doc_fitz.tobytes()
    doc_fitz.close()

    doc = DocumentLoader.carregar_bytes(pdf_bytes, nome_arquivo="atestado_curto.pdf")

    assert doc.requer_ocr is False
    assert "cuidados medicos" in doc.conteudo_texto


def test_formato_invalido():
    """Valida que formatos não suportados disparam ValueError"""
    with pytest.raises(ValueError):
        DocumentLoader.carregar_bytes(b"conteudo", nome_arquivo="arquivo.exe")


def test_arquivo_inexistente():
    """Valida que caminho inexistente dispara FileNotFoundError"""
    with pytest.raises(FileNotFoundError):
        DocumentLoader.carregar_arquivo("caminho/fantasma/inexistente.pdf")


# ==============================================================================
# TESTES DE INTEGRAÇÃO COM OS FIXTURES FÍSICOS REAIS DO WILLIAM
# ==============================================================================

def test_ingestao_fixture_william_com_senha():
    """Valida leitura direta do arquivo físico com senha dos fixtures do William."""
    pdf_senha = FIXTURES_DIR / "catalogo" / "Qualidade_Pdf_ComSenha" / "Qualidade_Pdf_ComSenha.pdf"
    assert pdf_senha.exists(), "Fixture com senha deve existir em tests/fixtures/catalogo/"

    with pytest.raises(DocumentoProtegidoError) as exc_info:
        DocumentLoader.carregar_arquivo(pdf_senha)

    assert exc_info.value.codigo == "PDF_PROTEGIDO"


def test_ingestao_fixture_william_corrompido():
    """Valida leitura direta do arquivo físico corrompido dos fixtures do William."""
    pdf_corrompido = FIXTURES_DIR / "catalogo" / "Qualidade_Pdf_Corrompido" / "Qualidade_Pdf_Corrompido.pdf"
    assert pdf_corrompido.exists(), "Fixture corrompido deve existir em tests/fixtures/catalogo/"

    with pytest.raises(DocumentoCorrompidoError) as exc_info:
        DocumentLoader.carregar_arquivo(pdf_corrompido)

    assert exc_info.value.codigo == "PDF_CORROMPIDO"


def test_ingestao_fixture_william_docx_nao_suportado():
    """Valida rejeição de formato .docx usando o arquivo real dos fixtures do William."""
    docx_file = FIXTURES_DIR / "catalogo" / "Validacao_ArquivoDocx" / "Validacao_ArquivoDocx.docx"
    assert docx_file.exists(), "Fixture DOCX deve existir em tests/fixtures/catalogo/"

    with pytest.raises(ValueError):
        DocumentLoader.carregar_arquivo(docx_file)


def test_ingestao_fixture_william_pdf_digital():
    """Valida carregamento de PDF digital da matriz demo dos fixtures do William."""
    pdf_demo = FIXTURES_DIR / "demo" / "Matriz_Receituario_Pdf" / "Matriz_Receituario_Pdf.pdf"
    assert pdf_demo.exists(), "Fixture demo deve existir em tests/fixtures/demo/"

    doc = DocumentLoader.carregar_arquivo(pdf_demo)
    assert doc.formato == "PDF"
    assert doc.total_paginas == 1
    assert doc.requer_ocr is False
    assert len(doc.conteudo_texto) > 100
    assert "RECEITUÁRIO MÉDICO" in doc.conteudo_texto or "HOSPITAL AURORA" in doc.conteudo_texto


def test_ingestao_fixture_william_imagem_multimodal():
    """Valida carregamento de imagem física JPG da matriz demo dos fixtures do William."""
    jpg_demo = FIXTURES_DIR / "demo" / "Matriz_Receituario_Imagem" / "Matriz_Receituario_Imagem.jpg"
    assert jpg_demo.exists(), "Fixture imagem deve existir em tests/fixtures/demo/"

    doc = DocumentLoader.carregar_arquivo(jpg_demo)
    assert doc.formato == "JPG"
    assert doc.requer_ocr is True
    assert doc.conteudo_bytes is not None
    assert len(doc.conteudo_bytes) > 0


def test_ingestao_fixture_william_imagem_webp():
    """Valida suporte a imagem no formato moderno WEBP (alinhado a Limite_Formato_Webp - A6)."""
    webp_fixture = FIXTURES_DIR / "catalogo" / "Limite_Formato_Webp" / "Limite_Formato_Webp.webp"
    assert webp_fixture.exists(), "Fixture WEBP deve existir em tests/fixtures/catalogo/"

    doc = DocumentLoader.carregar_arquivo(webp_fixture)
    assert doc.formato == "WEBP"
    assert doc.requer_ocr is True
    assert doc.conteudo_bytes is not None
    assert doc.metadados["mime"] == "image/webp"
    assert len(doc.conteudo_bytes) > 0
