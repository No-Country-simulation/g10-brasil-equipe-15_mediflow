"""
Testes rápidos de segurança para o campo opcional de chave Gemini no Streamlit.

Garante, sem inicializar o runtime pesado do Streamlit/AppTest, que:
1. A GEMINI_API_KEY configurada no servidor NUNCA pré-preenche o st.text_input
   nem é enviada/renderizada em qualquer chamada da camada de UI.
2. O AST de src/app/streamlit_app.py mantém value="" literal no campo de senha.
3. A resolução da chave efetiva prioriza a sobrescrita opcional do usuário
   e faz fallback seguro para a chave configurada exclusivamente no servidor.
"""

import ast
import runpy
import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from src.app.gemini_key import resolver_chave_gemini_efetiva

APP_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "app" / "streamlit_app.py"
)


class _SessionState(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class _StubStreamlit(types.ModuleType):
    """Stub leve do módulo streamlit que registra toda chamada feita à UI."""

    def __init__(self) -> None:
        super().__init__("streamlit")
        self.chamadas: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.session_state = _SessionState()
        self.sidebar = self

    def __enter__(self) -> "_StubStreamlit":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def _registrar(self, nome: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        self.chamadas.append((nome, args, kwargs))

    def columns(self, spec: Any, **kwargs: Any) -> list["_StubStreamlit"]:
        self._registrar("columns", (spec,), kwargs)
        qtd = spec if isinstance(spec, int) else len(spec)
        return [self for _ in range(qtd)]

    def tabs(self, labels: list[str], **kwargs: Any) -> list["_StubStreamlit"]:
        self._registrar("tabs", (labels,), kwargs)
        return [self for _ in labels]

    def container(self, *args: Any, **kwargs: Any) -> "_StubStreamlit":
        self._registrar("container", args, kwargs)
        return self

    def expander(self, *args: Any, **kwargs: Any) -> "_StubStreamlit":
        self._registrar("expander", args, kwargs)
        return self

    def spinner(self, *args: Any, **kwargs: Any) -> "_StubStreamlit":
        self._registrar("spinner", args, kwargs)
        return self

    def segmented_control(
        self,
        label: str,
        options: list[Any],
        default: Any = None,
        **kwargs: Any,
    ) -> Any:
        self._registrar("segmented_control", (label, options), {"default": default, **kwargs})
        return default if default is not None else options[0]

    def selectbox(self, label: str, options: list[Any], **kwargs: Any) -> Any:
        self._registrar("selectbox", (label, options), kwargs)
        return options[0]

    def text_input(self, label: str, value: str = "", **kwargs: Any) -> str:
        self._registrar("text_input", (label,), {"value": value, **kwargs})
        return value

    def file_uploader(self, *args: Any, **kwargs: Any) -> None:
        self._registrar("file_uploader", args, kwargs)
        return None

    def button(self, *args: Any, **kwargs: Any) -> bool:
        self._registrar("button", args, kwargs)
        return False

    def download_button(self, *args: Any, **kwargs: Any) -> bool:
        self._registrar("download_button", args, kwargs)
        return False

    def __getattr__(self, nome: str) -> Any:
        def _generico(*args: Any, **kwargs: Any) -> None:
            self._registrar(nome, args, kwargs)
            return None

        return _generico


def _contem_segredo(obj: Any, segredo: str) -> bool:
    if isinstance(obj, str):
        return segredo in obj
    if isinstance(obj, dict):
        return any(
            _contem_segredo(k, segredo) or _contem_segredo(v, segredo)
            for k, v in obj.items()
        )
    if isinstance(obj, (list, tuple, set)):
        return any(_contem_segredo(item, segredo) for item in obj)
    return segredo in repr(obj)


def test_ast_campo_chave_gemini_tem_value_vazio_literal():
    """Garante estaticamente que o st.text_input da chave Gemini usa value='' literal."""
    arvore = ast.parse(APP_PATH.read_text(encoding="utf-8"))
    chamadas_text_input = [
        no
        for no in ast.walk(arvore)
        if isinstance(no, ast.Call)
        and isinstance(no.func, ast.Attribute)
        and no.func.attr == "text_input"
    ]

    assert len(chamadas_text_input) == 1
    chamada = chamadas_text_input[0]
    kwargs = {kw.arg: kw.value for kw in chamada.keywords if kw.arg}

    assert "value" in kwargs
    assert isinstance(kwargs["value"], ast.Constant)
    assert kwargs["value"].value == ""

    assert "type" in kwargs
    assert isinstance(kwargs["type"], ast.Constant)
    assert kwargs["type"].value == "password"


def test_streamlit_nao_envia_chave_gemini_do_servidor_ao_navegador(monkeypatch):
    """Com GEMINI_API_KEY no servidor, o campo de senha inicia vazio e o segredo nunca chega à UI."""
    segredo_servidor = "AIza-segredo-servidor-nao-expor-99999"
    monkeypatch.setenv("GEMINI_API_KEY", segredo_servidor)
    fake_st = _StubStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", fake_st)

    with patch("dotenv.load_dotenv", return_value=False):
        runpy.run_path(str(APP_PATH), run_name="__streamlit_test__")

    chamadas_input = [
        (args, kwargs)
        for nome, args, kwargs in fake_st.chamadas
        if nome == "text_input" and args and "Chave Gemini API" in str(args[0])
    ]
    assert len(chamadas_input) == 1
    _, kwargs_input = chamadas_input[0]
    assert kwargs_input["value"] == ""
    assert kwargs_input["type"] == "password"
    assert "servidor" in kwargs_input["placeholder"].lower()

    for nome, args, kwargs in fake_st.chamadas:
        assert not _contem_segredo(args, segredo_servidor), (
            f"Segredo vazou em args de st.{nome}"
        )
        assert not _contem_segredo(kwargs, segredo_servidor), (
            f"Segredo vazou em kwargs de st.{nome}"
        )

    assert not _contem_segredo(dict(fake_st.session_state), segredo_servidor)

    legendas = [
        str(args[0])
        for nome, args, _ in fake_st.chamadas
        if nome == "caption" and args
    ]
    assert any("mantida apenas no backend" in cap for cap in legendas)


def test_streamlit_sem_chave_servidor_mantem_campo_vazio(monkeypatch):
    """Sem GEMINI_API_KEY no servidor, o campo de senha inicia vazio e não exibe aviso de chave ativa."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    fake_st = _StubStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", fake_st)

    with patch("dotenv.load_dotenv", return_value=False):
        runpy.run_path(str(APP_PATH), run_name="__streamlit_test__")

    chamadas_input = [
        (args, kwargs)
        for nome, args, kwargs in fake_st.chamadas
        if nome == "text_input" and args and "Chave Gemini API" in str(args[0])
    ]
    assert len(chamadas_input) == 1
    _, kwargs_input = chamadas_input[0]
    assert kwargs_input["value"] == ""

    legendas = [
        str(args[0])
        for nome, args, _ in fake_st.chamadas
        if nome == "caption" and args
    ]
    assert not any("mantida apenas no backend" in cap for cap in legendas)


@pytest.mark.parametrize(
    "api_key_custom,chave_env,esperado_chave,esperado_ativa",
    [
        ("", "AIza-servidor-valido", "AIza-servidor-valido", True),
        ("   ", "AIza-servidor-valido", "AIza-servidor-valido", True),
        ("  AIza-usuario-override  ", "AIza-servidor-valido", "AIza-usuario-override", True),
        ("AIza-usuario-unico", "", "AIza-usuario-unico", True),
        ("", "", None, False),
        ("", "sua_chave_aqui", None, False),
        ("   ", "sua_chave_gemini", None, False),
    ],
)
def test_resolver_chave_gemini_efetiva(
    api_key_custom,
    chave_env,
    esperado_chave,
    esperado_ativa,
):
    """Valida a precedência da chave opcional e o fallback seguro para a chave do servidor."""
    chave, ativa = resolver_chave_gemini_efetiva(api_key_custom, chave_env)
    assert chave == esperado_chave
    assert ativa is esperado_ativa
