"""
MediFlow — Schemas de Transporte da API REST (DTOs)
Modelos específicos para endpoints HTTP assíncronos e contratos de rede.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CriarTriagemTextoRequest(BaseModel):
    """Payload JSON para submissão de documento em texto puro (CT-001)."""
    documento_id: Optional[str] = Field(
        default=None,
        description="Identificador único opcional. Se omitido, o sistema gera automaticamente (RN-07)."
    )
    tipo_arquivo: Optional[str] = Field(
        default="TEXTO",
        description="Tipo de mídia informado (ex: TEXTO)."
    )
    documento_texto: Optional[str] = Field(
        default=None,
        description="Conteúdo em texto clínico do documento."
    )
    canal_origem: Optional[str] = Field(
        default="Prontuário",
        description="Canal de entrada ou sistema de origem (CT-005)."
    )
    metadados: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Metadados auxiliares arbitrários (não contaminam dados_extraidos)."
    )


class TriagemCriadaResponse(BaseModel):
    """Resposta imediata da submissão assíncrona (HTTP 202 Accepted)."""
    documento_id: str
    status: str = "RECEBIDO"
    status_url: str
    historico_url: str
    mensagem: str = "Documento aceito e enfileirado para processamento."


class StatusTriagemResponse(BaseModel):
    """Consulta rápida de status para polling de interface (React / Streamlit)."""
    documento_id: str
    status: str
    destinos: List[str] = Field(default_factory=list)
    requer_auditoria_humana: bool = False
    concluido: bool = False


class EventoHistorico(BaseModel):
    """Registro imutável na linha do tempo de auditoria (CT-070 a CT-072)."""
    evento_id: str
    documento_id: str
    tipo_evento: str
    criado_em: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    ator: str
    status_anterior: Optional[str] = None
    status_novo: str
    motivo: Optional[str] = None
    versao_esquema: str = "2.0.0"


class HealthResponse(BaseModel):
    """Resposta do health check operacional (CT-076)."""
    status: str = "healthy"
    versao: str = "2.0.0"
    servicos: Dict[str, str] = Field(default_factory=dict)


class ErroEnvelope(BaseModel):
    """Envelope padronizado de erro seguro (CT-077 e CT-080)."""
    codigo: str
    mensagem: str
    detalhes: Optional[Dict[str, Any]] = None
