"""
Converte o envelope da extração para a entrada oficial do workflow.

Não chama Gemini, API ou OCI.
Não calcula qualidade nem decide roteamento.
"""

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from pydantic import BaseModel

from src.workflow.state import EntradaWorkflow


def _copiar_bloco(valor: Any) -> Any:
    if isinstance(valor, BaseModel):
        # Preserva a diferença entre um campo informado
        # e um valor padrão criado pelo modelo.
        return valor.model_dump(
            mode="python",
            exclude_unset=True,
        )

    return deepcopy(valor)


def entrada_do_envelope(
    envelope: Mapping[str, Any],
    *,
    documento_id: str,
    classificacao: Any,
    limiar: float,
) -> EntradaWorkflow:
    """
    Adapta o envelope sem duplicar validações do workflow.

    Documento, classificação e limiar vêm da aplicação.
    Sinais obrigatórios ausentes são erros de integração.
    """
    if not isinstance(envelope, Mapping):
        raise TypeError(
            "O envelope deve ser um mapeamento."
        )

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

    if envelope["urgencia"] is None:
        raise ValueError(
            "O sinal de urgência do envelope não pode ser null."
        )

    payload = {
        "documento_id": documento_id,
        "classificacao": _copiar_bloco(classificacao),
        "dados_extraidos": _copiar_bloco(
            envelope["dados_clinicos"]
        ),
        "urgencia": deepcopy(envelope["urgencia"]),
        "qualidade": {
            "campos_incertos": deepcopy(
                envelope["campos_incertos"]
            ),
            "conflitos": deepcopy(
                envelope["conflitos"]
            ),
        },
    }

    return EntradaWorkflow.de_extracao(
        payload,
        limiar=limiar,
    )