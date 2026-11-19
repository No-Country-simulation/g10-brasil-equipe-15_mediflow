"""
MediFlow — Testes mínimos de CORS da API.
Confirma que as origens permitidas vêm da variável de ambiente CORS_ORIGINS
(padrão vazio = nenhuma origem externa autorizada).
"""
import importlib

import pytest
from starlette.testclient import TestClient

import src.api.main
import src.config


def _recarregar_app():
    """Recarrega config e main para que o middleware leia o CORS_ORIGINS atual."""
    importlib.reload(src.config)
    importlib.reload(src.api.main)
    return src.api.main.app


@pytest.fixture
def recarregar_com_env(monkeypatch):
    """Recarrega o app com o ambiente atual e restaura o estado original ao final."""
    yield _recarregar_app
    monkeypatch.undo()
    _recarregar_app()


def test_cors_padrao_nao_libera_origem_externa(monkeypatch, recarregar_com_env):
    """Sem CORS_ORIGINS, a resposta não traz access-control-allow-origin."""
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    client = TestClient(recarregar_com_env())

    response = client.get("/api/v1/health", headers={"Origin": "https://exemplo.com"})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_cors_origem_configurada_e_ecoada(monkeypatch, recarregar_com_env):
    """Origem listada em CORS_ORIGINS é ecoada; origem não listada continua bloqueada."""
    monkeypatch.setenv("CORS_ORIGINS", " https://a.com , ,https://b.com")
    client = TestClient(recarregar_com_env())

    permitida = client.get("/api/v1/health", headers={"Origin": "https://b.com"})
    negada = client.get("/api/v1/health", headers={"Origin": "https://exemplo.com"})

    assert src.config.CORS_ORIGINS == ["https://a.com", "https://b.com"]
    assert permitida.headers["access-control-allow-origin"] == "https://b.com"
    assert "access-control-allow-credentials" not in permitida.headers
    assert "access-control-allow-origin" not in negada.headers
