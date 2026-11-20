"""Testes mínimos da flag FIXTURE_MODE (score forçado de fixtures oficiais) na API."""
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from src.api.main import app

FIXTURE_TXT = (
    Path(__file__).resolve().parent / "fixtures" / "demo" / "Borda_Score_084" / "Borda_Score_084.txt"
)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("API_USAR_GEMINI", "false")
    return TestClient(app, raise_server_exceptions=False)


def _triar(client, texto):
    resposta = client.post("/api/v1/triagens", json={"documento_texto": texto})
    assert resposta.status_code == 202
    resultado = client.get(f"/api/v1/triagens/{resposta.json()['documento_id']}")
    assert resultado.status_code == 200
    return resultado.json()


def test_fixture_mode_ativo_forca_score_084_e_revisao_humana(client, monkeypatch):
    monkeypatch.setenv("FIXTURE_MODE", "true")
    triagem = _triar(client, FIXTURE_TXT.read_text(encoding="utf-8"))

    assert triagem["status"] == "EM_REVISAO"
    assert triagem["qualidade"]["score_extracao"] == 0.84
    assert triagem["qualidade"]["score_combinado"] == 0.84
    assert "FILA_REVISAO_HUMANA" in triagem["decisao_roteamento"]["destinos"]


def test_fixture_mode_ausente_nao_forca_score(client, monkeypatch):
    monkeypatch.delenv("FIXTURE_MODE", raising=False)
    triagem = _triar(client, FIXTURE_TXT.read_text(encoding="utf-8"))

    assert triagem["qualidade"]["score_combinado"] != 0.84


def test_fixture_mode_ativo_nao_altera_documento_comum(client, monkeypatch):
    texto = (
        "Receituário Médico\nPaciente: Maria da Silva, 45 anos.\n"
        "Dr. Carlos (CRM: 12345/SP)\nMedicamento: Amoxicilina 500mg."
    )
    monkeypatch.delenv("FIXTURE_MODE", raising=False)
    base = _triar(client, texto)
    monkeypatch.setenv("FIXTURE_MODE", "true")
    com_flag = _triar(client, texto)

    assert com_flag["qualidade"]["score_combinado"] == base["qualidade"]["score_combinado"]
    assert com_flag["status"] == base["status"]
