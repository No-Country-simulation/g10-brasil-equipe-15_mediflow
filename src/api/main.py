"""
MediFlow — Ponto de Entrada da API REST FastAPI
Configurações de middleware, CORS, tratamento global de erros seguros e rotas /api/v1.
"""
import logging
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.routes import router as api_v1_router
from src.schemas import CodigoErro

logger = logging.getLogger("mediflow.api")

app = FastAPI(
    title="MediFlow API",
    version="2.0.0",
    description="Agente Autônomo para Triagem, Extração e Roteamento de Documentos Clínicos",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configuração de CORS para suportar o Portal React SPA e a Bancada Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusão dos roteadores versionados
app.include_router(api_v1_router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Garante que qualquer HTTPException siga o envelope seguro da EPT."""
    detail = exc.detail
    if isinstance(detail, dict):
        codigo = detail.get("codigo", "ERRO_REQUISICAO")
        mensagem = detail.get("mensagem", str(exc.detail))
    else:
        codigo = "ERRO_REQUISICAO"
        mensagem = str(detail)

    return JSONResponse(
        status_code=exc.status_code,
        content={"codigo": codigo, "mensagem": mensagem},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Trata erros sintáticos e validações do Pydantic no corpo da requisição (CT-008, CT-012)."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "codigo": CodigoErro.CAMPOS_INVALIDOS.value,
            "mensagem": "Campos inválidos ou ausentes na requisição.",
            "detalhes": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Tratamento de exceções inesperadas (CT-077, CT-080):
    NUNCA expõe stack trace, credenciais OCI ou prompts internos para o cliente.
    """
    logger.exception("Erro interno não tratado no servidor: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "codigo": "ERRO_INTERNO",
            "mensagem": "Ocorreu um erro interno no servidor ao processar o documento. Tente novamente mais tarde.",
        },
    )


@app.get("/", tags=["Status"])
def root():
    return {
        "projeto": "MediFlow",
        "versao": "2.0.0",
        "status": "online",
        "documentacao": "/docs",
    }
