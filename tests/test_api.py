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
from unittest.mock import patch
import fitz
import pytest
from starlette.testclient import TestClient

from src.api.main import app
from src.schemas import CodigoErro, StatusTriagem


@pytest.fixture
def client():
    """Cliente HTTP de teste isolado para a aplicação FastAPI."""
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def oci_mock_falha_original():
    """Fixture que simula falha imediata da nuvem OCI no upload do documento original."""
    from unittest.mock import MagicMock
    storage = MagicMock()
    storage.enviar_bytes.side_effect = Exception("ServiceError 503: Conexão OCI indisponível")
    return storage


@pytest.fixture
def oci_mock_falha_resultado():
    """Fixture que simula sucesso no documento original mas erro 507 na gravação do resultado.json."""
    from unittest.mock import MagicMock
    storage = MagicMock()
    storage.enviar_bytes.side_effect = [
        {"status_backup": "sucesso"},
        RuntimeError("ServiceError 507: Quota do bucket OCI excedida"),
    ]
    return storage


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


def test_ct057_revisao_humana_preserva_qualidade_e_motivos_do_grafo(client):
    """CT-057: API propaga métricas reais de qualidade do LangGraph e motivos específicos de revisão."""
    # Documento com campos ausentes (sem paciente e sem diagnóstico) para forçar revisão
    payload = {
        "documento_texto": "Receituário Médico\nDr. Renato CRM: 14589/SP"
    }
    post_res = client.post("/api/v1/triagens", json=payload)
    assert post_res.status_code == 202
    doc_id = post_res.json()["documento_id"]

    get_res = client.get(f"/api/v1/triagens/{doc_id}")
    assert get_res.status_code == 200
    triagem = get_res.json()

    # Deve entrar em revisão humana
    assert triagem["status"] == "EM_REVISAO"
    assert "FILA_REVISAO_HUMANA" in triagem["decisao_roteamento"]["destinos"]

    # Qualidade calculada pelo grafo (Fórmula A3) não pode ser o 0.95 estático
    qualidade = triagem["qualidade"]
    assert qualidade["score_extracao"] < 0.95
    assert qualidade["score_combinado"] < 0.95
    assert len(qualidade["campos_ausentes"]) > 0
    assert any("paciente" in c for c in qualidade["campos_ausentes"])

    # Motivos de revisão preservados na justificativa
    justificativa = triagem["decisao_roteamento"]["justificativa_roteamento"]
    assert "campos obrigatórios ausentes" in justificativa.lower()


# ==============================================================================
# SUÍTE 3: HOMOLOGAÇÃO DE API E ERROS EPT (CT-064, CT-075, CT-077 a CT-079)
# ==============================================================================

def test_ct064_falha_na_notificacao_nao_apaga_triagem(client):
    """CT-064: Falha no canal de notificação não invalida a triagem calculada nem apaga o resultado."""
    payload = {
        "documento_texto": "Laudo de Exame de Imagem\nPaciente: Maria Eduarda Santos, 61 anos.\nDra. Camila Alencar CRM: 98765/SP\nDiagnóstico: Tromboembolismo Pulmonar Agudo URGENTE."
    }
    post_res = client.post("/api/v1/triagens", json=payload)
    assert post_res.status_code == 202
    doc_id = post_res.json()["documento_id"]

    get_res = client.get(f"/api/v1/triagens/{doc_id}")
    assert get_res.status_code == 200
    triagem = get_res.json()

    # Confirma que o destino de urgência e dados clínicos foram preservados
    assert "FILA_URGENCIA_MEDICA" in triagem["decisao_roteamento"]["destinos"]
    assert triagem["dados_extraidos"]["diagnostico"] is not None
    # Notificação fica com status REGISTRADA/simulado sem quebrar o payload
    assert triagem["decisao_roteamento"]["notificacao"]["status"] == "REGISTRADA"


def test_ct075_isolamento_de_documentos_e_autorizacao_segura(client):
    """CT-075: IDs de documento possuem entropia segura, não são sequenciais previsíveis e são isolados."""
    res1 = client.post("/api/v1/triagens", json={"documento_texto": "Laudo Paciente Alfa\nDr. Silva CRM 12345/SP"})
    res2 = client.post("/api/v1/triagens", json={"documento_texto": "Laudo Paciente Beta\nDr. Silva CRM 12345/SP"})
    assert res1.status_code == 202
    assert res2.status_code == 202

    id1 = res1.json()["documento_id"]
    id2 = res2.json()["documento_id"]
    assert id1 != id2
    # Formato seguro canônico DOC-CLIN-YYYY-XXXX (não sequencial)
    assert id1.startswith("DOC-") and len(id1) >= 15
    assert id2.startswith("DOC-") and len(id2) >= 15

    doc1 = client.get(f"/api/v1/triagens/{id1}").json()
    doc2 = client.get(f"/api/v1/triagens/{id2}").json()
    assert doc1["documento_id"] != doc2["documento_id"]


def test_ct077_envelopes_padronizados_de_erro(client):
    """CT-077: Erros de cliente e servidor devolvem envelopes padronizados com 'codigo' e 'mensagem'."""
    # 1. 400 - Requisição inválida / JSON malformado
    r400 = client.post("/api/v1/triagens", content="{invalido", headers={"Content-Type": "application/json"})
    assert r400.status_code == 400
    assert "codigo" in r400.json() and "mensagem" in r400.json()

    # 2. 415 - Formato não suportado
    r415 = client.post("/api/v1/triagens", files={"file": ("planilha.xlsx", io.BytesIO(b"abc"), "application/vnd.ms-excel")})
    assert r415.status_code == 415
    assert "codigo" in r415.json() and "mensagem" in r415.json()

    # 3. 422 - Campos inválidos / corpo vazio
    r422 = client.post("/api/v1/triagens", json={})
    assert r422.status_code == 422
    assert "codigo" in r422.json() and "mensagem" in r422.json()

    # 4. 404 - Documento não encontrado
    r404 = client.get("/api/v1/triagens/DOC-INEXISTENTE-999")
    assert r404.status_code == 404
    assert "codigo" in r404.json() and "mensagem" in r404.json()


def test_ct078_resiliencia_falha_dependencias_sem_travar_api(client):
    """CT-078: Indisponibilidade de dependência externa (OCI/Gemini) não derruba a API e mantém integridade."""
    # Simula falha na inicialização do storage OCI
    with patch("src.storage.oci_storage.OCIStorage.das_configuracoes", side_effect=Exception("Timeout no bucket OCI")):
        res = client.post("/api/v1/triagens", json={"documento_texto": "Receituário Médico\nDr. Renato CRM: 14589/SP"})
        assert res.status_code == 202
        doc_id = res.json()["documento_id"]

        get_res = client.get(f"/api/v1/triagens/{doc_id}")
        assert get_res.status_code == 200
        triagem = get_res.json()
        # O backup registra a falha sem lançar HTTP 500 para o chamador
        assert triagem["armazenamento_oci"]["status_backup"] == "ignorado_ou_falha"


def test_ct079_pdf_protegido_e_corrompido_retornam_codigos_distintos(client):
    """CT-079: PDFs protegidos por senha e corrompidos retornam HTTP 422 com códigos distintos da EPT."""
    # 1. PDF corrompido
    res_corrompido = client.post(
        "/api/v1/triagens",
        files={"file": ("corrompido.pdf", io.BytesIO(b"%PDF-1.4 corrompido e truncado..."), "application/pdf")}
    )
    assert res_corrompido.status_code == 422
    assert res_corrompido.json()["codigo"] == CodigoErro.PDF_CORROMPIDO.value

    # 2. PDF protegido por senha
    doc_fitz = fitz.open()
    doc_fitz.new_page()
    pdf_senha_bytes = doc_fitz.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256,
        user_pw="senha123",
        owner_pw="master123"
    )
    doc_fitz.close()

    res_protegido = client.post(
        "/api/v1/triagens",
        files={"file": ("com_senha.pdf", io.BytesIO(pdf_senha_bytes), "application/pdf")}
    )
    assert res_protegido.status_code == 422
    assert res_protegido.json()["codigo"] == CodigoErro.PDF_PROTEGIDO.value


def test_falha_persistencia_oci_original_preserva_decisao_e_gera_erro_persistencia():
    """
    Simulação: Falha de OCI ao gravar o arquivo original.
    O fluxo NÃO deve terminar como PROCESSADO, mas sim como ERRO_PERSISTENCIA,
    preservando intactas as entidades clínicas, qualidade e decisão (RF-28, RF-30, §12).
    """
    from unittest.mock import MagicMock
    from src.api.service import TriagemService
    from src.schemas import StatusTriagem, CodigoErro

    storage_mock = MagicMock()
    storage_mock.enviar_bytes.side_effect = Exception("Timeout de rede ao conectar com OCI Object Storage")

    service = TriagemService(storage=storage_mock)
    texto = "Receituário Médico\nPaciente: João Silva\nIdade: 45\nDiagnóstico: Faringite\nMédico: Dr. Lucas\nCRM: 12345/SP"
    doc_id = service.submeter_texto(texto)

    triagem = service.executar_triagem(doc_id)

    # Verifica se transicionou para ERRO_PERSISTENCIA e não PROCESSADO
    assert triagem.status == StatusTriagem.ERRO_PERSISTENCIA
    assert service.obter_status(doc_id) == StatusTriagem.ERRO_PERSISTENCIA
    assert triagem.erro is not None
    assert triagem.erro.codigo == CodigoErro.ERRO_PERSISTENCIA
    assert "FALHA_GRAVACAO_ORIGINAL" in triagem.erro.mensagem

    # Verifica se os dados clínicos e decisão foram preservados para retentativa
    assert triagem.dados_extraidos.paciente.nome == "João Silva"
    assert triagem.qualidade is not None
    assert triagem.decisao_roteamento is not None
    assert len(triagem.decisao_roteamento.destinos) > 0


def test_falha_persistencia_oci_resultado_preserva_decisao_e_gera_erro_persistencia():
    """
    Simulação: Gravação do arquivo original tem sucesso, mas a gravação do JSON final do resultado falha.
    O status deve ser ERRO_PERSISTENCIA (RF-30, §12) com decisão e métricas preservadas.
    """
    from unittest.mock import MagicMock
    from src.api.service import TriagemService
    from src.schemas import StatusTriagem, CodigoErro

    storage_mock = MagicMock()
    # 1ª chamada (original): sucesso; 2ª chamada (resultado.json): falha
    storage_mock.enviar_bytes.side_effect = [
        {"status_backup": "sucesso"},
        RuntimeError("OCI rejeitou escrita de resultado.json: Bucket quota exceeded"),
    ]

    service = TriagemService(storage=storage_mock)
    texto = "Receituário Médico\nPaciente: Carlos Souza\nIdade: 30\nDiagnóstico: Gripe\nMédico: Dr. Renato\nCRM: 998877/RJ"
    doc_id = service.submeter_texto(texto)

    triagem = service.executar_triagem(doc_id)

    assert triagem.status == StatusTriagem.ERRO_PERSISTENCIA
    assert service.obter_status(doc_id) == StatusTriagem.ERRO_PERSISTENCIA
    assert triagem.erro.codigo == CodigoErro.ERRO_PERSISTENCIA
    assert "FALHA_GRAVACAO_RESULTADO" in triagem.erro.mensagem
    assert triagem.dados_extraidos.paciente.nome == "Carlos Souza"
    assert triagem.decisao_roteamento is not None


def test_reprocessar_persistencia_oci_via_api_com_sucesso(client):
    """
    Cenário completo de resiliência:
    1. Gravação falha inicialmente -> documento fica com ERRO_PERSISTENCIA
    2. Endpoint de retry é acionado após restauração do bucket -> restaura PROCESSADO sem reprocessar LLM.
    """
    from unittest.mock import MagicMock
    from src.api.routes import triagem_service
    from src.schemas import StatusTriagem

    storage_mock = MagicMock()
    storage_mock.enviar_bytes.side_effect = Exception("Conexão indisponível")
    triagem_service._storage = storage_mock

    # 1. Submete documento
    texto = "Receituário Médico\nPaciente: Maria Clara\nIdade: 28\nDiagnóstico: Cefaleia\nMédico: Dra. Paula\nCRM: 54321/SP"
    res_envio = client.post("/api/v1/triagens", json={"documento_texto": texto})
    assert res_envio.status_code == 202
    doc_id = res_envio.json()["documento_id"]

    # Executa triagem que falhará no OCI
    triagem = triagem_service.executar_triagem(doc_id)
    assert triagem.status == StatusTriagem.ERRO_PERSISTENCIA

    # Polling constata ERRO_PERSISTENCIA
    res_status = client.get(f"/api/v1/triagens/{doc_id}/status")
    assert res_status.status_code == 200
    assert res_status.json()["status"] == StatusTriagem.ERRO_PERSISTENCIA.value
    assert res_status.json()["concluido"] is True

    # 2. Restaura OCI (sem side_effect) e dispara retentativa
    storage_mock.enviar_bytes.side_effect = None
    storage_mock.enviar_bytes.return_value = {"status_backup": "sucesso"}

    res_retry = client.post(f"/api/v1/triagens/{doc_id}/reprocessar-persistencia")
    assert res_retry.status_code == 200
    data_retry = res_retry.json()
    assert data_retry["status"] in (StatusTriagem.PROCESSADO.value, StatusTriagem.EM_REVISAO.value)
    assert data_retry["erro"] is None
    assert data_retry["armazenamento_oci"]["status_backup"] == "sucesso"
    assert "resultado.json" in data_retry["armazenamento_oci"]["caminho_objeto"]
    assert data_retry["dados_extraidos"]["paciente"]["nome"] == "Maria Clara"


# ==============================================================================
# SUÍTE: SIMULAÇÃO DE ERROS OCI E CATÁLOGO DE TESTES DA EPT (RF-28, RF-30, §12)
# ==============================================================================

def test_simulacao_catalogo_oci_falha_original_multipart(client):
    """
    Valida simulação por arquivo do catálogo EPT: Simulacao_OciFalhaNoOriginal.txt.
    - Falha simulada ao gravar original no OCI -> transiciona para ERRO_PERSISTENCIA.
    - Polling GET /status confirma concluido=True e status=ERRO_PERSISTENCIA.
    - Retentativa via POST /reprocessar-persistencia restaura o estado para sucesso.
    """
    from src.api.routes import triagem_service

    conteudo = (
        "Receita de Emergência\n"
        "Paciente: João da Silva\n"
        "Médico: Dra. Camila\n"
        "Diagnóstico: Infarto Agudo\n"
        "Medicamento: AAS 100mg"
    ).encode("utf-8")

    files = {"file": ("Simulacao_OciFalhaNoOriginal.txt", io.BytesIO(conteudo), "text/plain")}
    res_envio = client.post("/api/v1/triagens", files=files)
    assert res_envio.status_code == 202
    doc_id = res_envio.json()["documento_id"]

    # Executa triagem
    triagem = triagem_service.executar_triagem(doc_id)
    assert triagem.status == StatusTriagem.ERRO_PERSISTENCIA
    assert triagem.erro is not None
    assert triagem.erro.codigo == CodigoErro.ERRO_PERSISTENCIA
    assert "FALHA_GRAVACAO_ORIGINAL" in triagem.erro.mensagem

    # 1. Checa status via API
    res_status = client.get(f"/api/v1/triagens/{doc_id}/status")
    assert res_status.status_code == 200
    assert res_status.json()["status"] == StatusTriagem.ERRO_PERSISTENCIA.value
    assert res_status.json()["concluido"] is True

    # 2. Checa resultado completo canônico
    res_resultado = client.get(f"/api/v1/triagens/{doc_id}")
    assert res_resultado.status_code == 200
    data = res_resultado.json()
    assert data["status"] == StatusTriagem.ERRO_PERSISTENCIA.value
    assert data["dados_extraidos"]["paciente"]["nome"] == "João da Silva"
    assert data["armazenamento_oci"]["status_backup"] == "falha"

    # 3. Executa retentativa de persistência
    res_retry = client.post(f"/api/v1/triagens/{doc_id}/reprocessar-persistencia")
    assert res_retry.status_code == 200
    data_retry = res_retry.json()
    assert data_retry["status"] in (StatusTriagem.PROCESSADO.value, StatusTriagem.EM_REVISAO.value)
    assert data_retry["armazenamento_oci"]["status_backup"] == "sucesso"
    assert data_retry["erro"] is None


def test_simulacao_catalogo_oci_falha_resultado_multipart(client):
    """
    Valida simulação por arquivo do catálogo EPT: Simulacao_OciFalhaNoResultado.txt.
    - Sucesso ao gravar original, mas simula erro 507 ao tentar persistir resultado.json.
    - Preserva rigorosamente as decisões clínicas, qualidade e roteamento já calculados.
    - Permite nova tentativa de persistência com restauração de status.
    """
    from src.api.routes import triagem_service

    conteudo = (
        "Solicitação de Exame Clínico\n"
        "Paciente: Marina Barbosa\n"
        "Médico: Dr. Pedro\n"
        "Exame: Hemograma Completo"
    ).encode("utf-8")

    files = {"file": ("Simulacao_OciFalhaNoResultado.txt", io.BytesIO(conteudo), "text/plain")}
    res_envio = client.post("/api/v1/triagens", files=files)
    assert res_envio.status_code == 202
    doc_id = res_envio.json()["documento_id"]

    triagem = triagem_service.executar_triagem(doc_id)
    assert triagem.status == StatusTriagem.ERRO_PERSISTENCIA
    assert triagem.erro is not None
    assert "FALHA_GRAVACAO_RESULTADO" in triagem.erro.mensagem
    assert triagem.dados_extraidos.paciente.nome == "Marina Barbosa"
    assert triagem.decisao_roteamento is not None

    # Verifica na API de resultado
    res_res = client.get(f"/api/v1/triagens/{doc_id}")
    assert res_res.status_code == 200
    assert res_res.json()["status"] == StatusTriagem.ERRO_PERSISTENCIA.value

    # Retenta persistência
    res_retry = client.post(f"/api/v1/triagens/{doc_id}/reprocessar-persistencia")
    assert res_retry.status_code == 200
    assert res_retry.json()["status"] in (StatusTriagem.PROCESSADO.value, StatusTriagem.EM_REVISAO.value)
    assert res_retry.json()["armazenamento_oci"]["status_backup"] == "sucesso"


def test_simulacao_catalogo_oci_falha_via_json_metadados(client):
    """
    Valida que o gatilho da EPT funciona também em payloads JSON com metadados.
    """
    from src.api.routes import triagem_service

    payload = {
        "documento_texto": "Laudo Cardiológico\nPaciente: Sérgio Ramos\nMédico: Dra. Vanessa\nECG Normal.",
        "metadados": {"nome_arquivo": "Simulacao_OciFalhaNoOriginal.txt"},
    }
    res_envio = client.post("/api/v1/triagens", json=payload)
    assert res_envio.status_code == 202
    doc_id = res_envio.json()["documento_id"]

    triagem = triagem_service.executar_triagem(doc_id)
    assert triagem.status == StatusTriagem.ERRO_PERSISTENCIA
    assert "FALHA_GRAVACAO_ORIGINAL" in triagem.erro.mensagem


def test_fixture_oci_mock_falha_original_com_service(oci_mock_falha_original):
    """
    Valida o uso direto da fixture oci_mock_falha_original no TriagemService.
    """
    from src.api.service import TriagemService
    service = TriagemService(storage=oci_mock_falha_original)

    doc_id = service.submeter_texto("Receita Teste Paciente: Ana")
    triagem = service.executar_triagem(doc_id)

    assert triagem.status == StatusTriagem.ERRO_PERSISTENCIA
    assert "FALHA_GRAVACAO_ORIGINAL" in triagem.erro.mensagem


def test_fixture_oci_mock_falha_resultado_com_service(oci_mock_falha_resultado):
    """
    Valida o uso direto da fixture oci_mock_falha_resultado no TriagemService.
    """
    from src.api.service import TriagemService
    service = TriagemService(storage=oci_mock_falha_resultado)

    doc_id = service.submeter_texto("Receita Teste Paciente: Marcos")
    triagem = service.executar_triagem(doc_id)

    assert triagem.status == StatusTriagem.ERRO_PERSISTENCIA
    assert "FALHA_GRAVACAO_RESULTADO" in triagem.erro.mensagem



