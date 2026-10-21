"""
Testes unitários para o módulo de ingestão de documentos (DocumentLoader).
Valida leitura de PDFs clínicos, extração de texto, metadados e tratamento de erros.
"""
from pathlib import Path
import pytest
from src.ingestion import DocumentLoader, DocumentoIngerido

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "data" / "samples"


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
    """Valida carregamento direto de bytes (simulando upload via Streamlit/FastAPI)"""
    pdf_path = SAMPLES_DIR / "02_laudo_urgencia_tep.pdf"
    with open(pdf_path, "rb") as f:
        bytes_data = f.read()

    doc = DocumentLoader.carregar_bytes(bytes_data, nome_arquivo="upload_urgencia.pdf")

    assert doc.nome_arquivo == "upload_urgencia.pdf"
    assert doc.formato == "PDF"
    assert doc.tamanho_bytes == len(bytes_data)
    assert "Maria Eduarda Santos" in doc.conteudo_texto


def test_formato_invalido():
    """Valida que formatos não suportados disparam ValueError"""
    with pytest.raises(ValueError):
        DocumentLoader.carregar_bytes(b"conteudo", nome_arquivo="arquivo.exe")


def test_arquivo_inexistente():
    """Valida que caminho inexistente dispara FileNotFoundError"""
    with pytest.raises(FileNotFoundError):
        DocumentLoader.carregar_arquivo("caminho/fantasma/inexistente.pdf")
