"""
MediFlow - Schemas e Modelos Pydantic para Documentos Clínicos
Define o contrato de dados oficial para toda a aplicação.
"""
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class NivelPrioridade(str, Enum):
    ROTINA = "Rotina"
    URGENTE = "Urgente"
    AMBIGUO = "Ambiguidade/Revisão Humana"


class DestinoRoteamento(str, Enum):
    EMERGENCIA = "Fila_Emergencia_Medica"
    AUDITORIA = "Auditoria_Autorizacoes"
    FARMACIA = "Farmacia_Hospitalar"
    PRONTUARIO = "Prontuario_Eletronico"
    REVISAO_HUMANA = "Fila_Revisao_Humana"


class Paciente(BaseModel):
    nome: Optional[str] = Field(None, description="Nome completo do paciente")
    idade: Optional[int] = Field(None, description="Idade do paciente em anos")


class MedicoSolicitante(BaseModel):
    nome: Optional[str] = Field(None, description="Nome do médico solicitante")
    crm: Optional[str] = Field(None, description="Número de CRM com UF (ex: 145892-SP)")


class ClassificacaoClinica(BaseModel):
    tipo_documento: str = Field(
        ...,
        description="Categoria: Laudo de Exame, Receituário, Guia TISS/TUSS, Atestado Médico, etc."
    )
    especialidade: Optional[str] = Field(
        None,
        description="Especialidade médica identificada (ex: Cardiologia, Radiologia, Pneumologia)"
    )
    nivel_prioridade: NivelPrioridade = Field(
        ...,
        description="Classificação de gravidade e prioridade do caso"
    )
    score_confianca_classificacao: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Score de confiança do modelo na classificação (0.0 a 1.0)"
    )


class DadosExtraidos(BaseModel):
    paciente: Paciente = Field(default_factory=Paciente)
    medico_solicitante: MedicoSolicitante = Field(default_factory=MedicoSolicitante)
    exame_realizado: Optional[str] = Field(None, description="Nome do exame complementar realizado, se houver")
    medicamentos: Optional[List[str]] = Field(default=None, description="Lista de medicamentos prescritos com dosagens")
    diagnostico_principal: Optional[str] = Field(None, description="Hipótese diagnóstica ou conclusão clínica")
    cid_sugerido: Optional[str] = Field(None, description="Código CID-10 identificado ou sugerido (ex: I26.9)")
    achados_criticos: Optional[str] = Field(None, description="Achados de urgência ou sinais de alerta")
    inconsistencias_detectadas: Optional[List[str]] = Field(
        default=None,
        description="Lista de inconformidades (ex: dados ilegíveis, CRM ausente)"
    )


class Notificacao(BaseModel):
    canal: str = Field(..., description="Canal de alerta (ex: Alerta_Plantao_Medico, Email, Slack)")
    mensagem: str = Field(..., description="Texto do alerta gerado para a equipe médica")


class DecisaoRoteamento(BaseModel):
    destino_principal: DestinoRoteamento = Field(
        ...,
        description="Fila ou departamento hospitalar para onde o documento foi direcionado"
    )
    requer_auditoria_humana: bool = Field(
        ...,
        description="Sinaliza se o caso precisa de aprovação manual por médico/auditor (Human-in-the-Loop)"
    )
    justificativa_roteamento: str = Field(
        ...,
        description="Explicação clínica e operacional que fundamentou a decisão"
    )
    notificacao_gerada: Optional[Notificacao] = Field(
        None,
        description="Notificação automática disparada em caso de urgência"
    )


class ArmazenamentoOCI(BaseModel):
    bucket: str = Field(default="mediflow-documentos-clinicos")
    caminho_objeto: str = Field(
        ...,
        description="Caminho dentro do bucket (ex: processados/urgentes/DOC-2026.json)"
    )
    status_backup: str = Field(default="pendente", description="Status: pendente, sucesso ou falha")


class ResultadoTriagemClinica(BaseModel):
    status: str = Field(default="processado", description="Status geral do fluxo: processado, pendente_auditoria, erro")
    documento_id: str = Field(..., description="Identificador único do documento (ex: DOC-CLIN-2026-8942)")
    canal_origem: Optional[str] = Field(None, description="Canal de entrada (ex: Pronto_Socorro, Ambulatorio, Web)")
    classificacao: ClassificacaoClinica
    dados_extraidos: DadosExtraidos
    decisao_roteamento: DecisaoRoteamento
    armazenamento_oci: Optional[ArmazenamentoOCI] = None
