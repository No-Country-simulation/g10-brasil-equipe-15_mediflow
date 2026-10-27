"""
Módulo de Ingestão de Documentos Clínicos (MediFlow).
Responsável pelo carregamento seguro, extração de texto, tratamento de encoding,
validação de limites e preparação multimodal para o pipeline de IA.
"""
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, Union, Tuple
from pydantic import BaseModel, Field

try:
    import pymupdf as fitz
except ImportError:
    import fitz


# ==============================================================================
# EXCEÇÕES DE DOMÍNIO (ALINHADAS AOS REQUISITOS DO EDITAL E DO CATÁLOGO)
# ==============================================================================

class IngestaoError(Exception):
    """Exceção base para erros durante a etapa de ingestão de documentos."""
    def __init__(self, codigo: str, mensagem: str):
        super().__init__(mensagem)
        self.codigo = codigo
        self.mensagem = mensagem


class TamanhoExcedidoError(IngestaoError):
    """Disparado quando o arquivo excede o limite máximo de bytes ou páginas permitidos."""
    def __init__(self, tamanho_bytes: Optional[int] = None, limite_bytes: Optional[int] = None, mensagem: Optional[str] = None):
        if mensagem:
            msg = mensagem
        elif tamanho_bytes is not None and limite_bytes is not None:
            msg = f"O arquivo possui {tamanho_bytes / (1024*1024):.2f}MB, excedendo o limite de {limite_bytes / (1024*1024):.2f}MB."
        else:
            msg = "Arquivo excede o limite máximo permitido."
        super().__init__(
            codigo="ARQUIVO_MAIOR_QUE_LIMITE",
            mensagem=msg
        )


class DocumentoProtegidoError(IngestaoError):
    """Disparado quando o documento PDF possui proteção por senha."""
    def __init__(self, mensagem: str = "O documento PDF está protegido por senha e não pode ser processado sem credenciais."):
        super().__init__(codigo="PDF_PROTEGIDO", mensagem=mensagem)


class DocumentoCorrompidoError(IngestaoError):
    """Disparado quando o arquivo está incompleto, truncado ou com estrutura inválida."""
    def __init__(self, mensagem: str = "O arquivo está corrompido ou truncado e não pôde ser aberto."):
        super().__init__(codigo="PDF_CORROMPIDO", mensagem=mensagem)


# ==============================================================================
# MODELO PADRONIZADO DE SAÍDA DA INGESTÃO
# ==============================================================================

class DocumentoIngerido(BaseModel):
    """Representação padronizada e segura de um documento clínico na esteira do MediFlow."""
    documento_id: str = Field(..., description="Identificador único no formato DOC-XXXXXXXX")
    nome_arquivo: str = Field(..., description="Nome original do arquivo submetido")
    formato: str = Field(..., description="Extensão detectada: PDF, TXT, PNG, JPG, JPEG")
    tamanho_bytes: int = Field(..., ge=0, description="Tamanho exato do arquivo em bytes")
    total_paginas: int = Field(default=1, ge=1, description="Número de páginas do documento")
    conteudo_texto: str = Field(default="", description="Texto bruto extraído do documento")
    requer_ocr: bool = Field(default=False, description="Sinaliza se o documento é puramente imagem e exige visão computacional/OCR")
    conteudo_bytes: Optional[bytes] = Field(default=None, repr=False, description="Bytes da mídia original (essencial para envio multimodal à LLM)")
    metadados: Dict[str, Any] = Field(default_factory=dict, description="Metadados técnicos e de qualidade")


# ==============================================================================
# CARREGADOR ROBUSTO DE DOCUMENTOS
# ==============================================================================

class DocumentLoader:
    """Carregador robusto com proteções de segurança, encoding e integridade."""

    FORMATOS_SUPORTADOS = {".pdf", ".txt", ".png", ".jpg", ".jpeg", ".webp"}
    LIMITE_MAXIMO_BYTES = 10 * 1024 * 1024  # 10 MB (alinhado aos testes de limites do MVP)
    LIMITE_MAXIMO_PAGINAS = 20              # Máximo 20 páginas por documento

    @staticmethod
    def gerar_documento_id() -> str:
        """Gera um identificador único de documento no formato padrão DOC-XXXXXXXX"""
        return f"DOC-{uuid.uuid4().hex[:8].upper()}"

    @classmethod
    def validar_limite_tamanho(cls, tamanho_bytes: int) -> None:
        """Valida se o tamanho do arquivo respeita a política de segurança de 10MB."""
        if tamanho_bytes > cls.LIMITE_MAXIMO_BYTES:
            raise TamanhoExcedidoError(tamanho_bytes=tamanho_bytes, limite_bytes=cls.LIMITE_MAXIMO_BYTES)

    @classmethod
    def carregar_arquivo(
        cls,
        caminho_arquivo: Union[str, Path],
        documento_id: Optional[str] = None
    ) -> DocumentoIngerido:
        """
        Carrega um arquivo a partir de um caminho em disco com verificações de integridade.
        """
        path = Path(caminho_arquivo)
        if not path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {path}")

        extensao = path.suffix.lower()
        if extensao not in cls.FORMATOS_SUPORTADOS:
            raise ValueError(f"Formato não suportado: {extensao}. Formatos válidos: {cls.FORMATOS_SUPORTADOS}")

        tamanho_bytes = path.stat().st_size
        cls.validar_limite_tamanho(tamanho_bytes)
        doc_id = documento_id or cls.gerar_documento_id()

        with open(path, "rb") as f:
            bytes_data = f.read()

        return cls.carregar_bytes(
            conteudo_bytes=bytes_data,
            nome_arquivo=path.name,
            documento_id=doc_id
        )

    @classmethod
    def carregar_bytes(
        cls,
        conteudo_bytes: bytes,
        nome_arquivo: str,
        documento_id: Optional[str] = None
    ) -> DocumentoIngerido:
        """
        Carrega um documento a partir de bytes em memória (upload web/API) com blindagem completa.
        """
        extensao = Path(nome_arquivo).suffix.lower()
        if extensao not in cls.FORMATOS_SUPORTADOS:
            raise ValueError(f"Formato não suportado: '{extensao}'. Suportados: {cls.FORMATOS_SUPORTADOS}")

        tamanho_bytes = len(conteudo_bytes)
        if tamanho_bytes == 0:
            raise IngestaoError(codigo="ARQUIVO_VAZIO", mensagem="O arquivo enviado está vazio (0 bytes).")
        cls.validar_limite_tamanho(tamanho_bytes)
        doc_id = documento_id or cls.gerar_documento_id()

        if extensao == ".pdf":
            texto, total_paginas, requer_ocr, meta = cls._extrair_pdf_blindado(conteudo_bytes)
        elif extensao == ".txt":
            texto, total_paginas, requer_ocr, meta = cls._extrair_txt_blindado(conteudo_bytes)
        else:
            # Imagens (PNG/JPG/JPEG/WEBP): Validação de assinatura/magic bytes e preparação multimodal
            cls._validar_imagem_blindada(conteudo_bytes, extensao)
            texto, total_paginas, requer_ocr, meta = "", 1, True, {"tipo": "imagem", "mime": f"image/{extensao.replace('.', '')}"}

        return DocumentoIngerido(
            documento_id=doc_id,
            nome_arquivo=nome_arquivo,
            formato=extensao.replace(".", "").upper(),
            tamanho_bytes=tamanho_bytes,
            total_paginas=total_paginas,
            conteudo_texto=texto.strip(),
            requer_ocr=requer_ocr,
            conteudo_bytes=conteudo_bytes,
            metadados=meta
        )

    @staticmethod
    def _validar_imagem_blindada(conteudo_bytes: bytes, extensao: str) -> None:
        """Valida assinaturas de imagem (magic bytes) para barrar injeção de arquivos comuns mascarados."""
        ext = extensao.lower()
        valido = False
        if ext == ".png" and conteudo_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            valido = True
        elif ext in {".jpg", ".jpeg"} and conteudo_bytes.startswith(b"\xff\xd8\xff"):
            valido = True
        elif ext == ".webp" and conteudo_bytes.startswith(b"RIFF") and b"WEBP" in conteudo_bytes[:16]:
            valido = True

        if not valido:
            raise DocumentoCorrompidoError(
                f"IMAGEM_CORROMPIDA: O arquivo com extensão '{ext}' não possui assinatura binária válida de imagem."
            )

    @staticmethod
    def _extrair_pdf_blindado(conteudo_bytes: bytes) -> Tuple[str, int, bool, Dict[str, Any]]:
        """Abre e extrai o PDF tratando senhas, corrupção e heurística de texto."""
        if not conteudo_bytes.startswith(b"%PDF"):
            raise IngestaoError(
                codigo="MIME_INVALIDO",
                mensagem="Arquivo com extensão .pdf possui assinatura binária incompatível (inconsistência de MIME)."
            )
        try:
            doc = fitz.open(stream=conteudo_bytes, filetype="pdf")
        except Exception as e:
            raise DocumentoCorrompidoError(f"PDF_CORROMPIDO: Estrutura inválida de arquivo PDF ({str(e)})")

        with doc:
            if doc.is_encrypted:
                raise DocumentoProtegidoError("PDF_PROTEGIDO: O arquivo está criptografado/protegido por senha.")

            total_paginas = len(doc)
            if total_paginas == 0:
                raise DocumentoCorrompidoError("PDF_CORROMPIDO: O arquivo PDF não possui páginas válidas.")
            if total_paginas > DocumentLoader.LIMITE_MAXIMO_PAGINAS:
                raise TamanhoExcedidoError(
                    mensagem=f"PDF válido de {total_paginas} páginas: excede o limite de {DocumentLoader.LIMITE_MAXIMO_PAGINAS} páginas fixado para o MVP (A6)."
                )

            textos_paginas = []
            paginas_vazias = 0

            for pagina in doc:
                try:
                    txt = pagina.get_text("text") or ""
                    textos_paginas.append(txt)
                    if not txt.strip():
                        paginas_vazias += 1
                except Exception:
                    paginas_vazias += 1

            texto_completo = "\n\n--- Quebra de Página ---\n\n".join(textos_paginas) if total_paginas > 1 else "".join(textos_paginas)
            
            # Heurística precisa: requer OCR se o texto limpo for vazio ou se alguma página não contiver texto nativo
            texto_limpo = texto_completo.strip()
            requer_ocr = (len(texto_limpo) == 0) or (paginas_vazias > 0)

            metadados = {
                "autor": doc.metadata.get("author", "") if doc.metadata else "",
                "titulo": doc.metadata.get("title", "") if doc.metadata else "",
                "total_caracteres": len(texto_limpo),
                "paginas_sem_texto": paginas_vazias,
                "criptografado": False
            }

            return texto_completo, total_paginas, requer_ocr, metadados

    @staticmethod
    def _extrair_txt_blindado(conteudo_bytes: bytes) -> Tuple[str, int, bool, Dict[str, Any]]:
        """Decodifica texto com fallback inteligente: UTF-8 -> Latin-1 (ISO-8859-1) -> Windows-1252."""
        encodings = ["utf-8", "iso-8859-1", "windows-1252"]
        texto_decodificado = None
        encoding_usado = None

        for enc in encodings:
            try:
                texto_decodificado = conteudo_bytes.decode(enc)
                encoding_usado = enc
                break
            except UnicodeDecodeError:
                continue

        if texto_decodificado is None:
            texto_decodificado = conteudo_bytes.decode("utf-8", errors="replace")
            encoding_usado = "utf-8 (fallback replace)"

        if not texto_decodificado.strip():
            raise IngestaoError(codigo="CONTEUDO_TXT_VAZIO", mensagem="O arquivo TXT não possui conteúdo textual legível.")

        metadados = {
            "encoding_detectado": encoding_usado,
            "total_caracteres": len(texto_decodificado)
        }
        return texto_decodificado, 1, False, metadados

