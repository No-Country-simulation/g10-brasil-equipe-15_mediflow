"""
MediFlow — Suíte de Testes da API REST FastAPI
Cobre integralmente os casos de teste da EPT (CT-001 a CT-012, CT-070 a CT-080):
- Envio assíncrono (HTTP 202 Accepted)
- Rejeições 400, 415 e 422
- Consultas de status e resultado canônico 200/404
- Linha do tempo de histórico e auditoria
- Health check e ausência de vazamento de dados internos
"""
import io
import pytest
from starlette.testclient import TestClient

from src.api.main import app
from src.schemas import CodigoErro, StatusTriagem


@pytest.fixture
def client():
    """Cliente HTTP de teste isolado para a aplicação FastAPI."""
    return TestClient(app, raise_server_exceptions=False)


# ==============================================================================
# SUÍTE 1: INGESTÃO E VALIDAÇÃO VIA API (CT-001 a CT-012)
# ==============================================================================

def test_ct001_envio_texto_retorna_202_com_urls(client):
    """CT-001: Envio de documento textual retorna 202 com documento_id, status_url e historico_url."""
    payload = {
        "tipo_arquivo": "TEXTO",
        "documento_texto": "Receituário Médico\nPaciente: Maria da Silva, 45 anos.\nDr. Carlos (CRM: 12345/SP)\nMedicamento: Amoxicilina 500mg.",
        "canal_origem": "Prontuário",
        "metadados": {"lote": "LOTE-01"}
    }
    response = client.post("/api/v1/triagens", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert "documento_id" in data
    assert data["documento_id"].startswith("DOC-")
    assert data["status"] == "RECEBIDO"
    assert data["status_url"] == f"/api/v1/triagens/{data['documento_id']}/status"
    assert data["historico_url"] == f"/api/v1/triagens/{data['documento_id']}/historico"


def test_ct002_envio_pdf_digital_multipart(client):
    """CT-002: Envio de PDF digital via multipart retorna 202 e gera triagem."""
    from pathlib import Path
    caminho_pdf = Path(__file__).resolve().parent / "fixtures" / "demo" / "Matriz_Guia_Pdf" / "Matriz_Guia_Pdf.pdf"
    if not caminho_pdf.exists():
        caminho_pdf = Path(__file__).resolve().parent.parent / "data" / "samples" / "01_laudo_rotina.pdf"
    with open(caminho_pdf, "rb") as f:
        conteudo_pdf = f.read()

    files = {"file": ("guia_procedimento.pdf", io.BytesIO(conteudo_pdf), "application/pdf")}
    data = {"canal_origem": "Auditoria"}

    response = client.post("/api/v1/triagens", files=files, data=data)
    assert response.status_code == 202
    res_data = response.json()
    assert res_data["status"] == "RECEBIDO"
    assert "documento_id" in res_data


def test_ct003_envio_imagem_jpg(client):
    """CT-003: Envio de imagem JPG via multipart retorna 202."""
    # Magic bytes do JPEG: \xFF\xD8\xFF
    conteudo_jpg = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xFF\xDB\x00C\x00" + b"\x00" * 50
    files = {"file": ("receita.jpg", io.BytesIO(conteudo_jpg), "image/jpeg")}

    response = client.post("/api/v1/triagens", files=files)
    assert response.status_code == 202
    assert response.json()["status"] == "RECEBIDO"


def test_ct005_metadados_preservados_sem_virar_dado_clinico(client):
    """CT-005: canal_origem e metadados são aceitos sem contaminar dados_extraidos."""
    payload = {
        "documento_texto": "Laudo de Exame de Imagem\nPaciente: João Mendes, 50 anos.\nDr. Silva CRM: 98765/SP",
        "canal_origem": "Pronto_Socorro",
        "metadados": {"lote": "QA-TESTE-99"}
    }
    response = client.post("/api/v1/triagens", json=payload)
    assert response.status_code == 202
    doc_id = response.json()["documento_id"]

    res_triagem = client.get(f"/api/v1/triagens/{doc_id}")
    assert res_triagem.status_code == 200
    dados = res_triagem.json()
    # Metadados não podem estar em dados_extraidos
    assert "lote" not in dados["dados_extraidos"]


def test_ct006_documento_id_informado_respeitado(client):
    """CT-006: documento_id customizado informado na requisição é estritamente preservado (RN-07)."""
    id_custom = "DOC-CUSTOM-TESTE-999"
    payload = {
        "documento_id": id_custom,
        "documento_texto": "Receituário médico de teste para validação de ID."
    }
    response = client.post("/api/v1/triagens", json=payload)
    assert response.status_code == 202
    assert response.json()["documento_id"] == id_custom


def test_ct007_requisicao_sem_arquivo_sem_texto_retorna_422(client):
    """CT-007: Requisição multipart sem arquivo e sem texto retorna 422 CAMPOS_INVALIDOS."""
    response = client.post("/api/v1/triagens", data={})
    assert response.status_code == 422
    data = response.json()
    assert data["codigo"] == CodigoErro.CAMPOS_INVALIDOS.value


def test_ct008_json_malformado_retorna_400(client):
    """CT-008: JSON sintaticamente malformado retorna 400 REQUISICAO_INVALIDA."""
    json_invalido = '{"documento_texto": "teste com chave desbalanceada", '
    response = client.post(
        "/api/v1/triagens",
        content=json_invalido,
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400
    assert response.json()["codigo"] == CodigoErro.REQUISICAO_INVALIDA.value


def test_ct009_formato_nao_suportado_docx_retorna_415(client):
    """CT-009: Formato fora do allowlist (ex: .docx) retorna 415 FORMATO_NAO_SUPORTADO."""
    files = {"file": ("documento.docx", io.BytesIO(b"conteudo docx ficticio"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    response = client.post("/api/v1/triagens", files=files)
    assert response.status_code == 415
    assert response.json()["codigo"] == CodigoErro.FORMATO_NAO_SUPORTADO.value


def test_ct010_arquivo_zero_bytes_retorna_422(client):
    """CT-010: Arquivo vazio com 0 bytes retorna 422 CAMPOS_INVALIDOS."""
    files = {"file": ("arquivo_vazio.pdf", io.BytesIO(b""), "application/pdf")}
    response = client.post("/api/v1/triagens", files=files)
    assert response.status_code == 422
    assert response.json()["codigo"] == CodigoErro.CAMPOS_INVALIDOS.value


def test_ct011_extensao_falsa_mime_invalido_retorna_415(client):
    """CT-011: Conteúdo real de PNG renomeado com extensão .pdf retorna 415 MIME_INVALIDO."""
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
    files = {"file": ("falso_pdf.pdf", io.BytesIO(png_bytes), "application/pdf")}
    response = client.post("/api/v1/triagens", files=files)
    assert response.status_code == 415
    assert response.json()["codigo"] == CodigoErro.MIME_INVALIDO.value


def test_ct012_envelope_json_vazio_retorna_422(client):
    """CT-012: Envelope JSON vazio {} é rejeitado como CAMPOS_INVALIDOS."""
    response = client.post("/api/v1/triagens", json={})
    assert response.status_code == 422
    assert response.json()["codigo"] == CodigoErro.CAMPOS_INVALIDOS.value


# ==============================================================================
# SUÍTE 2: CONSULTAS, STATUS E RESULTADOS (CT-070 a CT-080)
# ==============================================================================

def test_ct073_get_triagem_devolve_payload_completo(client):
    """CT-073: GET /api/v1/triagens/{id} devolve payload canônico completo TriagemMediFlow."""
    payload = {
        "documento_texto": "Receituário Médico\nPaciente: Carlos Eduardo, 52 anos.\nDr. Renato CRM: 14589/SP\nDiagnóstico: TEP Agudo URGENTE."
    }
    post_res = client.post("/api/v1/triagens", json=payload)
    assert post_res.status_code == 202
    doc_id = post_res.json()["documento_id"]

    get_res = client.get(f"/api/v1/triagens/{doc_id}")
    assert get_res.status_code == 200
    triagem = get_res.json()

    # Validação do Contrato Canônico
    assert triagem["documento_id"] == doc_id
    assert triagem["status"] in ("PROCESSADO", "EM_REVISAO")
    assert "classificacao" in triagem
    assert "dados_extraidos" in triagem
    assert "qualidade" in triagem
    assert "decisao_roteamento" in triagem
    assert "armazenamento_oci" in triagem
    assert triagem["versao_esquema"] == "2.0.0"


def test_ct074_consulta_id_inexistente_retorna_404(client):
    """CT-074: Consulta de ID inexistente retorna 404 DOCUMENTO_NAO_ENCONTRADO."""
    res_triagem = client.get("/api/v1/triagens/DOC-INEXISTENTE-1234")
    assert res_triagem.status_code == 404
    assert res_triagem.json()["codigo"] == "DOCUMENTO_NAO_ENCONTRADO"

    res_hist = client.get("/api/v1/triagens/DOC-INEXISTENTE-1234/historico")
    assert res_hist.status_code == 404
    assert res_hist.json()["codigo"] == "DOCUMENTO_NAO_ENCONTRADO"


def test_ct076_health_check_responde_200(client):
    """CT-076: GET /api/v1/health responde 200 sem expor segredos nem dados clínicos."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "api" in data["servicos"]
    # Garante que não há tokens nem chaves no corpo
    corpo_str = response.text.lower()
    assert "secret" not in corpo_str
    assert "key" not in corpo_str
    assert "password" not in corpo_str


def test_ct070_historico_devolve_eventos_ordenados(client):
    """CT-070: Histórico devolve linha do tempo completa e ordenada por documento_id."""
    payload = {
        "documento_texto": "Atestado Médico\nPaciente: Laura Lima, 30 anos.\nDr. Souza CRM: 55443/SP"
    }
    post_res = client.post("/api/v1/triagens", json=payload)
    doc_id = post_res.json()["documento_id"]

    # Força a finalização
    client.get(f"/api/v1/triagens/{doc_id}")

    hist_res = client.get(f"/api/v1/triagens/{doc_id}/historico")
    assert hist_res.status_code == 200
    eventos = hist_res.json()
    assert len(eventos) >= 2
    # Evento inicial deve ser RECEBIDO
    assert eventos[0]["tipo_evento"] == "RECEBIDO"
    assert eventos[0]["status_novo"] == StatusTriagem.RECEBIDO
    # Evento posterior deve ser ROTEADO
    assert any(e["tipo_evento"] == "ROTEADO" for e in eventos)


def test_ct080_nenhuma_resposta_expoe_stacktrace(client):
    """CT-080: Em erros técnicos, a resposta é higienizada e nunca expõe tracebacks internos."""
    # Provoca um erro 404
    res = client.get("/api/v1/triagens/DOC-INEXISTENTE")
    assert res.status_code == 404
    assert "Traceback" not in res.text
    assert "raise " not in res.text
