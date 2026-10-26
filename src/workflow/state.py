"""
Estado interno do workflow Mediflow.

Reutiliza o contrato oficial.
Não representa a resposta final da API.
"""

from math import isfinite
from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.schemas import (
    ClassificacaoClinica,
    DadosExtraidos,
    DestinoRoteamento,
)

class ConflitoWorkflow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo: str = Field(min_length=1)
    gravidade: Literal["ALTA", "MEDIA", "BAIXA"]
    descricao: str = ""
    campos: list[str] = Field(default_factory=list)

class EntradaWorkflow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documento_id: str = Field(min_length=1)
    classificacao: ClassificacaoClinica
    dados_extraidos: DadosExtraidos

    # Sinais estruturados produzidos pela análise.
    # O grafo não deduz urgência por palavras isoladas.
    urgencia: Literal["SIM", "NAO", "INDETERMINADO"] | None = None

    campos_ausentes: list[str] = Field(default_factory=list)
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

    @field_validator("campos_incertos", "campos_ausentes")
    @classmethod
    def normalizar_campos(cls, valores: list[str]) -> list[str]:
        return sorted({
            valor.strip() 
            for valor in valores 
            if valor.strip()
        })

    @model_validator(mode="after")
    def alinhar_sinais(self):
        dados = self.dados_extraidos
        interna = getattr(dados, "urgencia", None)
        interna = getattr(interna, "value", interna)
        explicita = "urgencia" in dados.model_fields_set
        if explicita and self.urgencia is not None and self.urgencia != interna:
            raise ValueError("Urgência divergente entre a entrada e dados_extraidos.")
        self.urgencia = interna if explicita else (self.urgencia or interna or "INDETERMINADO")
        # Copia o modelo para não modificar o objeto pertencente à extração.
        if hasattr(dados, "urgencia"):
            self.dados_extraidos = dados.model_copy(
                deep=True, update={"urgencia": type(dados.urgencia)(self.urgencia)}
            )
        score = self.classificacao.score_confianca_classificacao
        if not isfinite(score):
            raise ValueError("O score de classificação deve ser finito.")
        return self

    @classmethod
    def de_extracao(cls, payload: dict, *, limiar: float = 0.85):
        """Recebe blocos extraídos sem executar TriagemMediFlow.aplicar_regras.

        Scores ilustrativos da massa e decisões sugeridas pela LLM não entram
        no cálculo. O limiar vem da aplicação, nunca do documento clínico.
        """
        qualidade = payload.get("qualidade") or {}
        dados = payload["dados_extraidos"]
        if "medico" not in DadosExtraidos.model_fields and any(
            campo in dados for campo in ("medico", "diagnostico", "exames", "urgencia")
        ):
            raise ValueError(
                "Integre o contrato harmonizado antes de receber seus campos canônicos."
            )
        return cls(
            documento_id=payload["documento_id"],
            classificacao=payload["classificacao"],
            dados_extraidos=payload["dados_extraidos"],
            urgencia=payload.get("urgencia"),
            campos_ausentes=qualidade.get("campos_ausentes", []),
            campos_incertos=qualidade.get("campos_incertos", []),
            conflitos=qualidade.get("conflitos", []),
            limiar=limiar,
        )


class QualidadeWorkflow(BaseModel):
    conflitos: list[ConflitoWorkflow] = Field(default_factory=list)
    observacoes: list[str] = Field(default_factory=list)
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
