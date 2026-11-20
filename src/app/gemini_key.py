"""
Resolução segura da chave Gemini para a camada Streamlit.

Não depende do Streamlit. Mantém a chave do servidor exclusivamente
no backend, permitindo sobrescrita opcional pelo usuário na sessão.
"""

from typing import Optional


def resolver_chave_gemini_efetiva(
    api_key_custom: str,
    chave_env: str,
) -> tuple[Optional[str], bool]:
    """Resolve a chave efetiva no backend priorizando a sobrescrita opcional do usuário."""
    chave_usuario = (api_key_custom or "").strip()
    chave_servidor = (chave_env or "").strip()
    tem_chave_servidor = bool(
        chave_servidor and not chave_servidor.startswith("sua_chave")
    )

    if chave_usuario:
        return chave_usuario, True
    if tem_chave_servidor:
        return chave_servidor, True
    return None, False
