"""
Converte o envelope Gemini em entrada do workflow.

Reutiliza o contrato e as validações existentes.
Não calcula scores, não escolhe destinos e não persiste dados.
"""

from collections.abc import Mapping
from typing import Any

from src.schemas import ClassificacaoClinica
from src.workflow.state import EntradaWorkflow


def entrada_de_envelope_gemini(
    *,
    documento_id: str,
    classificacao: ClassificacaoClinica | dict[str, Any],
    envelope: Mapping[str, Any],
    limiar: float,
) -> EntradaWorkflow:
    """
    O documento_id e o limiar vêm da aplicação,
    nunca do conteúdo extraído pelo Gemini.
    """
    obrigatorios = {
        "dados_clinicos",
        "urgencia",
        "campos_incertos",
        "conflitos",
    }

    faltantes = obrigatorios.difference(envelope)

    if faltantes:
        raise ValueError(
            "Envelope incompleto: "
            + ", ".join(sorted(faltantes))
        )

    if envelope["dados_clinicos"] is None:
        raise ValueError(
            "dados_clinicos não pode ser None."
        )

    if envelope["urgencia"] not in (
        "SIM",
        "NAO",
        "INDETERMINADO",
    ):
        raise ValueError(
            "Urgência do envelope inválida."
        )

    # O adaptador apenas mapeia o retorno do serviço.
    # As validações restantes pertencem à EntradaWorkflow.
    return EntradaWorkflow.de_extracao(
        {
            "documento_id": documento_id,
            "classificacao": classificacao,
            "dados_extraidos": envelope["dados_clinicos"],
            "urgencia": envelope["urgencia"],
            "qualidade": {
                "campos_incertos": envelope["campos_incertos"],
                "conflitos": envelope["conflitos"],
            },
        },
        limiar=limiar,
    )