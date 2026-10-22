"""
Estado interno do workflow Mediflow.

Reutiliza o contrato oficial.
Não representa a resposta final da API.
"""

from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.schemas import (
    ClassificacaoClinica,
    DadosExtraidos,
    DestinoRoteamento,
)

class ConflitoWorkflow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo: str = Field(min_length=1)
    gravidade: Literal["ALTA", "MEDIA", "BAIXA"]
    descricao: str = Field(min_length=1)
    campos: list[str] = Field(default_factory=list)

class EntradaWorkflow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documento_id: str = Field(min_length=1)
    classificacao: ClassificacaoClinica
    dados_extraidos: DadosExtraidos

    # Sinais estruturados produzidos pela análise.
    # O grafo não deduz urgência por palavras isoladas.
    urgencia: Literal["SIM", "NAO", "INDETERMINADO"]

    campos_incertos: list[str] = Field(default_factory=list)
    conflitos: list[ConflitoWorkflow] = Field(default_factory=list)

    # O backend deverá fornecer a configuração da aplicação.
    limiar: float = Field(
        default=0.85, 
        ge=0, 
        le=1, 
        allow_inf_nan=False,
    )

    @field_validator("documento_id")
    @classmethod
    def validar_documento_id(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("documento_id não pode estar vazio.")
        return valor

    @field_validator("campos_incertos")
    @classmethod
    def normalizar_campos(cls, valores: list[str]) -> list[str]:
        return sorted({
            valor.strip() 
            for valor in valores 
            if valor.strip()
        })


class QualidadeWorkflow(BaseModel):
    campos_ausentes: list[str]
    campos_incertos: list[str]
    score_classificacao: float = Field(
        ge=0, le=1, allow_inf_nan=False
    )
    score_extracao: float = Field(
        ge=0, le=1, allow_inf_nan=False
    )
    score_combinado: float = Field(
        ge=0, le=1, allow_inf_nan=False
    )
    limiar_aplicado: float = Field(
        ge=0, le=1, allow_inf_nan=False
    )
    motivos_revisao: list[str]

class DecisaoWorkflow(BaseModel):
    destinos: list[DestinoRoteamento] = Field(min_length=1)
    requer_auditoria_humana: bool
    justificativa: str
    regras_acionadas: list[str]
    alerta_simulado: bool

    # É etapa interna, não confirma armazenamento nem envio ao sistema hospitalar.
    etapa: Literal["DECISAO_CALCULADA"] = "DECISAO_CALCULADA"

class EstadoWorkflow(TypedDict, total=False):
    entrada: EntradaWorkflow
    qualidade: QualidadeWorkflow
    decisao: DecisaoWorkflow