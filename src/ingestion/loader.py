"""
Módulo de Ingestão de Documentos Clínicos (MediFlow).
Responsável pelo carregamento, extração de texto e extração de metadados de arquivos PDF, imagens e texto.
"""
import os
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, Union, Tuple
from pydantic import BaseModel, Field

try:
    import pymupdf as fitz
except ImportError:
    import fitz


class DocumentoIngerido(BaseModel):
    """Representação padronizada de um documento clínico ingerido na esteira do MediFlow."""
    documento_id: str = Field(..., description="Identificador único gerado para o documento (ex: DOC-8F31A92B)")
    nome_arquivo: str = Field(..., description="Nome original do arquivo submetido")
    formato: str = Field(..., description="Extensão/formato detectado: PDF, TXT, PNG, JPG")
    tamanho_bytes: int = Field(..., ge=0, description="Tamanho do arquivo em bytes")
    total_paginas: int = Field(default=1, ge=1, description="Número de páginas do documento")
    conteudo_texto: str = Field(..., description="Texto bruto extraído do documento")
    requer_ocr: bool = Field(default=False, description="Indica se o documento é puramente escaneado e precisa de OCR visual")
    metadados: Dict[str, Any] = Field(default_factory=dict, description="Metadados adicionais do arquivo")


class DocumentLoader:
    """Carregador e extrator de texto para documentos clínicos."""

    FORMATOS_SUPORTADOS = {".pdf", ".txt", ".png", ".jpg", ".jpeg"}

    @staticmethod
    def gerar_documento_id() -> str:
        """Gera um ID padronizado no formato DOC-XXXXXXXX"""
        return f"DOC-{uuid.uuid4().hex[:8].upper()}"

    @classmethod
    def carregar_arquivo(
        cls,
        caminho_arquivo: Union[str, Path],
        documento_id: Optional[str] = None
    ) -> DocumentoIngerido:
        """
        Carrega um arquivo a partir de um caminho em disco e extrai seu conteúdo.
        
        Args:
            caminho_arquivo: Caminho absoluto ou relativo para o documento.
            documento_id: Identificador opcional. Se None, será gerado automaticamente.
            
        Returns:
            DocumentoIngerido contendo o texto extraído e metadados.
        """
        path = Path(caminho_arquivo)
        if not path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {path}")

        extensao = path.suffix.lower()
        if extensao not in cls.FORMATOS_SUPORTADOS:
            raise ValueError(f"Formato não suportado: {extensao}. Formatos válidos: {cls.FORMATOS_SUPORTADOS}")

        tamanho_bytes = path.stat().st_size
        doc_id = documento_id or cls.gerar_documento_id()

        if extensao == ".pdf":
            texto, total_paginas, requer_ocr, meta = cls._extrair_pdf(path)
        elif extensao == ".txt":
            texto, total_paginas, requer_ocr, meta = cls._extrair_txt(path)
        else:
            # Imagens (PNG/JPG): texto nativo é vazio, requer OCR multimodal
            texto, total_paginas, requer_ocr, meta = "", 1, True, {"tipo": "imagem"}

        return DocumentoIngerido(
            documento_id=doc_id,
            nome_arquivo=path.name,
            formato=extensao.replace(".", "").upper(),
            tamanho_bytes=tamanho_bytes,
            total_paginas=total_paginas,
            conteudo_texto=texto.strip(),
            requer_ocr=requer_ocr,
            metadados=meta
        )

    @classmethod
    def carregar_bytes(
        cls,
        conteudo_bytes: bytes,
        nome_arquivo: str,
        documento_id: Optional[str] = None
    ) -> DocumentoIngerido:
        """
        Carrega um documento diretamente a partir de bytes em memória (ex: upload via Streamlit ou FastAPI).
        """
        extensao = Path(nome_arquivo).suffix.lower()
        if extensao not in cls.FORMATOS_SUPORTADOS:
            raise ValueError(f"Formato não suportado: {extensao}")

        doc_id = documento_id or cls.gerar_documento_id()
        tamanho_bytes = len(conteudo_bytes)

        if extensao == ".pdf":
            texto, total_paginas, requer_ocr, meta = cls._extrair_pdf_bytes(conteudo_bytes)
        elif extensao == ".txt":
            texto = conteudo_bytes.decode("utf-8", errors="replace")
            total_paginas = 1
            requer_ocr = False
            meta = {"encoding": "utf-8"}
        else:
            texto, total_paginas, requer_ocr, meta = "", 1, True, {"tipo": "imagem"}

        return DocumentoIngerido(
            documento_id=doc_id,
            nome_arquivo=nome_arquivo,
            formato=extensao.replace(".", "").upper(),
            tamanho_bytes=tamanho_bytes,
            total_paginas=total_paginas,
            conteudo_texto=texto.strip(),
            requer_ocr=requer_ocr,
            metadados=meta
        )

    @staticmethod
    def _extrair_pdf(caminho: Path) -> Tuple[str, int, bool, Dict[str, Any]]:
        """Extrai texto e metadados de um PDF via PyMuPDF a partir do caminho."""
        with fitz.open(str(caminho)) as doc:
            return DocumentLoader._processar_documento_fitz(doc)

    @staticmethod
    def _extrair_pdf_bytes(conteudo_bytes: bytes) -> Tuple[str, int, bool, Dict[str, Any]]:
        """Extrai texto e metadados de um PDF via PyMuPDF a partir de bytes."""
        with fitz.open(stream=conteudo_bytes, filetype="pdf") as doc:
            return DocumentLoader._processar_documento_fitz(doc)

    @staticmethod
    def _processar_documento_fitz(doc: fitz.Document) -> Tuple[str, int, bool, Dict[str, Any]]:
        total_paginas = len(doc)
        textos_paginas = []
        paginas_sem_texto = 0

        for pagina in doc:
            texto_pag = pagina.get_text("text") or ""
            textos_paginas.append(texto_pag)
            if len(texto_pag.strip()) < 20:
                paginas_sem_texto += 1

        texto_completo = "\n\n--- Quebra de Página ---\n\n".join(textos_paginas) if total_paginas > 1 else "".join(textos_paginas)
        
        # Se a maioria das páginas não possui texto digital, trata-se de documento escaneado/imagem
        requer_ocr = (len(texto_completo.strip()) < 50) or (paginas_sem_texto == total_paginas)

        metadados = {
            "autor": doc.metadata.get("author", ""),
            "titulo": doc.metadata.get("title", ""),
            "criador": doc.metadata.get("creator", ""),
            "paginas_sem_texto": paginas_sem_texto,
            "total_caracteres": len(texto_completo)
        }

        return texto_completo, total_paginas, requer_ocr, metadados

    @staticmethod
    def _extrair_txt(caminho: Path) -> Tuple[str, int, bool, Dict[str, Any]]:
        with open(caminho, "r", encoding="utf-8", errors="replace") as f:
            texto = f.read()
        return texto, 1, False, {"encoding": "utf-8", "total_caracteres": len(texto)}
