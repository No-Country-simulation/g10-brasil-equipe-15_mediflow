"""
MediFlow — Rotas da API REST (/api/v1)
Implementa os endpoints assíncronos de triagem, consulta de status, histórico e health check.
"""
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import JSONResponse

from src.ingestion import IngestaoError
from src.schemas import CodigoErro, TriagemMediFlow
from src.api.schemas import (
    CriarTriagemTextoRequest,
    TriagemCriadaResponse,
    StatusTriagemResponse,
    EventoHistorico,
    HealthResponse,
    ErroEnvelope,
)
from src.api.service import triagem_service

router = APIRouter(prefix="/api/v1", tags=["Triagem Clínica"])


@router.post(
    "/triagens",
    response_model=TriagemCriadaResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submissão Assíncrona de Documento Clínico (JSON ou Multipart)",
    responses={
        202: {"description": "Documento aceito e enfileirado para processamento."},
        400: {"model": ErroEnvelope, "description": "Requisição ou JSON malformado."},
        413: {"model": ErroEnvelope, "description": "Arquivo maior que o limite (10 MB)."},
        415: {"model": ErroEnvelope, "description": "Formato não suportado ou MIME inválido."},
        422: {"model": ErroEnvelope, "description": "Campos obrigatórios ausentes ou arquivo vazio."},
    },
)
async def submeter_triagem(
    request: Request,
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(default=None),
    documento_id: Optional[str] = Form(default=None),
    canal_origem: Optional[str] = Form(default="Prontuário"),
    documento_texto: Optional[str] = Form(default=None),
):
    """
    Submissão assíncrona de documento para triagem clínica:
    - Aceita payload JSON (`application/json`) para envio textual (CT-001).
    - Aceita `multipart/form-data` para envio de arquivos PDF, imagens ou texto (CT-002, CT-003).
    - Retorna HTTP 202 com URLs de acompanhamento (CT-001).
    """
    content_type = request.headers.get("content-type", "")

    # Cenário A: Requisição em formato JSON (CT-001, CT-008, CT-012)
    if "application/json" in content_type:
        try:
            body_bytes = await request.body()
            if not body_bytes or not body_bytes.strip():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"codigo": CodigoErro.CAMPOS_INVALIDOS.value, "mensagem": "Corpo JSON vazio."},
                )
            dados = json.loads(body_bytes.decode("utf-8"))
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"codigo": CodigoErro.REQUISICAO_INVALIDA.value, "mensagem": "JSON malformado."},
            )

        if not dados or not isinstance(dados, dict) or len(dados) == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"codigo": CodigoErro.CAMPOS_INVALIDOS.value, "mensagem": "Envelope JSON vazio."},
            )

        texto = dados.get("documento_texto")
        if not texto or not str(texto).strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "codigo": CodigoErro.CAMPOS_INVALIDOS.value,
                    "mensagem": "É preciso enviar documento_texto ou arquivo.",
                },
            )

        doc_id_informado = dados.get("documento_id")
        origem = dados.get("canal_origem", "Prontuário")
        meta = dados.get("metadados", {})

        try:
            doc_id = triagem_service.submeter_texto(
                texto=str(texto),
                documento_id=doc_id_informado,
                canal_origem=origem,
                metadados=meta,
            )
        except IngestaoError as e:
            raise _tratar_erro_ingestao(e)

        background_tasks.add_task(triagem_service.executar_triagem, doc_id)

        return TriagemCriadaResponse(
            documento_id=doc_id,
            status="RECEBIDO",
            status_url=f"/api/v1/triagens/{doc_id}/status",
            historico_url=f"/api/v1/triagens/{doc_id}/historico",
            mensagem="Documento textual aceito e enfileirado para processamento.",
        )

    # Cenário B: Requisição Multipart / Form-Data (CT-002, CT-003, CT-007, CT-010)
    if file is not None:
        conteudo = await file.read()
        if len(conteudo) == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"codigo": CodigoErro.CAMPOS_INVALIDOS.value, "mensagem": "Arquivo vazio (0 bytes)."},
            )

        nome = file.filename or "documento.pdf"
        try:
            doc_id = triagem_service.submeter_arquivo(
                conteudo=conteudo,
                nome_arquivo=nome,
                documento_id=documento_id,
                canal_origem=canal_origem or "Upload",
            )
        except (IngestaoError, ValueError) as e:
            raise _tratar_erro_ingestao(e)

        background_tasks.add_task(triagem_service.executar_triagem, doc_id)

        return TriagemCriadaResponse(
            documento_id=doc_id,
            status="RECEBIDO",
            status_url=f"/api/v1/triagens/{doc_id}/status",
            historico_url=f"/api/v1/triagens/{doc_id}/historico",
            mensagem=f"Arquivo '{nome}' aceito e enfileirado para processamento.",
        )

    # Caso receba documento_texto via form-data
    if documento_texto and documento_texto.strip():
        try:
            doc_id = triagem_service.submeter_texto(
                texto=documento_texto,
                documento_id=documento_id,
                canal_origem=canal_origem or "Prontuário",
            )
        except IngestaoError as e:
            raise _tratar_erro_ingestao(e)

        background_tasks.add_task(triagem_service.executar_triagem, doc_id)

        return TriagemCriadaResponse(
            documento_id=doc_id,
            status="RECEBIDO",
            status_url=f"/api/v1/triagens/{doc_id}/status",
            historico_url=f"/api/v1/triagens/{doc_id}/historico",
            mensagem="Documento textual aceito e enfileirado para processamento.",
        )

    # CT-007: Nem arquivo nem texto enviados
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "codigo": CodigoErro.CAMPOS_INVALIDOS.value,
            "mensagem": "É preciso enviar arquivo ou documento_texto.",
        },
    )


@router.get(
    "/triagens/{documento_id}",
    summary="Consulta Resultado Completo da Triagem (CT-073)",
    responses={
        200: {"description": "Payload completo TriagemMediFlow."},
        404: {"model": ErroEnvelope, "description": "Documento não encontrado."},
    },
)
def obter_resultado_triagem(documento_id: str):
    """Retorna o payload completo da triagem no estado terminal (CT-073)."""
    # Se ainda estiver em processamento pendente, executa sincronamente para responder
    status_atual = triagem_service.obter_status(documento_id)
    if status_atual is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "codigo": "DOCUMENTO_NAO_ENCONTRADO",
                "mensagem": f"Documento '{documento_id}' não encontrado.",
            },
        )

    triagem = triagem_service.obter_triagem(documento_id)
    if not triagem:
        # Finaliza processamento pendente
        triagem = triagem_service.executar_triagem(documento_id)

    return triagem.model_dump(mode="json")


@router.get(
    "/triagens/{documento_id}/status",
    response_model=StatusTriagemResponse,
    summary="Polling de Status de Processamento",
)
def obter_status_triagem(documento_id: str):
    """Consulta leve de status para acompanhamento de tela."""
    status_atual = triagem_service.obter_status(documento_id)
    if status_atual is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "codigo": "DOCUMENTO_NAO_ENCONTRADO",
                "mensagem": f"Documento '{documento_id}' não encontrado.",
            },
        )

    triagem = triagem_service.obter_triagem(documento_id)
    destinos = [d.value for d in triagem.decisao_roteamento.destinos] if triagem else []
    requer_auditoria = triagem.decisao_roteamento.requer_auditoria_humana if triagem else False

    return StatusTriagemResponse(
        documento_id=documento_id,
        status=status_atual,
        destinos=destinos,
        requer_auditoria_humana=requer_auditoria,
        concluido=(status_atual in ("PROCESSADO", "EM_REVISAO", "ERRO_PROCESSAMENTO")),
    )


@router.get(
    "/triagens/{documento_id}/historico",
    response_model=List[EventoHistorico],
    summary="Linha do Tempo e Auditoria de Eventos (CT-070 a CT-072)",
)
def obter_historico_triagem(documento_id: str):
    """Retorna eventos cronológicos de auditoria para o documento_id informado."""
    status_atual = triagem_service.obter_status(documento_id)
    if status_atual is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "codigo": "DOCUMENTO_NAO_ENCONTRADO",
                "mensagem": f"Histórico do documento '{documento_id}' não encontrado.",
            },
        )

    return triagem_service.obter_historico(documento_id)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check de Disponibilidade Operacional (CT-076)",
)
def health_check():
    """Endpoint de prontidão e saúde dos serviços."""
    return HealthResponse(
        status="healthy",
        versao="2.0.0",
        servicos={
            "api": "ok",
            "langgraph": "ok",
            "oci_storage": "ok",
        },
    )


def _tratar_erro_ingestao(erro: Exception) -> HTTPException:
    """Mapeia exceções da camada de ingestão para respostas HTTP canônicas seguras."""
    msg = getattr(erro, "mensagem", None) or str(erro)
    code = getattr(erro, "codigo", None)
    if hasattr(code, "value"):
        code = code.value
    code = str(code) if code else ""

    if "não suportado" in msg.lower() or "não suportada" in msg.lower() or code == CodigoErro.FORMATO_NAO_SUPORTADO.value:
        return HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "codigo": CodigoErro.FORMATO_NAO_SUPORTADO.value,
                "mensagem": "Formatos aceitos: PDF, JPG, PNG, WEBP e TXT.",
            },
        )
    if "inconsistência" in msg.lower() or "inconsistente" in msg.lower() or code == CodigoErro.MIME_INVALIDO.value:
        return HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "codigo": CodigoErro.MIME_INVALIDO.value,
                "mensagem": "Conteúdo real incompatível com a extensão do arquivo.",
            },
        )
    if "10.00 mb" in msg.lower() or code == CodigoErro.ARQUIVO_MAIOR_QUE_LIMITE.value:
        return HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "codigo": CodigoErro.ARQUIVO_MAIOR_QUE_LIMITE.value,
                "mensagem": "Arquivo excede o limite operacional de 10.00 MB (Regra A6).",
            },
        )
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"codigo": CodigoErro.CAMPOS_INVALIDOS.value, "mensagem": msg},
    )
