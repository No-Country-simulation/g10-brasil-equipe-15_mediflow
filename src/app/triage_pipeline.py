"""
Conecta o serviço de extração ao agente.

Não depende do Streamlit.
Não calcula qualidade nem decide roteamento.
Não acessa o OCI.
"""

from typing import Any

from src.workflow.extraction_adapter import (
    entrada_do_envelope,
)
from src.workflow.graph import criar_grafo


def processar_documento_com_agente(
    *,
    servico: Any,
    documento_id: str,
    conteudo_texto: str = "",
    conteudo_bytes: bytes | None = None,
    mime_type: str | None = None,
    limiar: float,
) -> dict[str, Any]:
    """
    O limiar vem da aplicação.
    As regras permanecem no workflow existente.
    """
    argumentos = {
        "conteudo_texto": conteudo_texto,
        "conteudo_bytes": conteudo_bytes,
        "mime_type": mime_type,
    }

    classificacao = servico.classificar_documento(
        **argumentos
    )

    envelope = (
        servico.extrair_dados_clinicos_envelope(
            **argumentos
        )
    )

    entrada = entrada_do_envelope(
        envelope,
        documento_id=documento_id,
        classificacao=classificacao,
        limiar=limiar,
    )

    estado = criar_grafo().invoke(
        {"entrada": entrada}
    )

    return {
        "classificacao": entrada.classificacao,
        "dados_clinicos": entrada.dados_extraidos,
        "estado_workflow": estado,
    }