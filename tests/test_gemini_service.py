"""
MediFlow — Testes Unitários e de Resiliência do GeminiService (PR #12)
Arquivo: tests/test_gemini_service.py

Valida:
- Protocolo de transporte REST e timeout de 15s
- Saída estruturada Pydantic v2 (ClassificacaoDocumento e DadosClinicosExtraidos)
- Duplo fallback (retry entre modelos e fail-safe para revisão humana)
- Tratamento de exceções e JSON malformado
"""
import json
import pytest
from unittest.mock import MagicMock, patch

from src.services.gemini_service import GeminiService
from src.schemas.clinical import (
    ClassificacaoDocumento,
    DadosClinicosExtraidos,
    TipoDocumentoEnum,
    NivelPrioridadeEnum,
)


class TestGeminiService:
    """Suíte de testes de unidade e resiliência para o GeminiService."""

    def test_inicializacao_com_valores_padrao(self):
        """Verifica a inicialização padrão com o modelo gemini-3.8-flash."""
        service = GeminiService(api_key="chave_teste_mock")
        assert service.api_key == "chave_teste_mock"
        assert service.model_name == "gemini-3.8-flash"

    def test_configuracao_transporte_rest(self):
        """Verifica se genai.configure utiliza transport='rest' no Windows."""
        with patch("src.services.gemini_service.genai") as mock_genai:
            GeminiService(api_key="minha_chave_mock")
            mock_genai.configure.assert_called_with(api_key="minha_chave_mock", transport="rest")

    def test_classificacao_sucesso_com_pydantic_v2(self):
        """Verifica a classificação bem-sucedida com validação estruturada Pydantic v2."""
        payload_mock = {
            "tipo_documento": "LAUDO_EXAME_IMAGEM",
            "especialidade": "Radiologia",
            "nivel_prioridade": "Urgente",
            "score_confianca_classificacao": 0.98,
        }

        mock_response = MagicMock()
        mock_response.text = json.dumps(payload_mock)

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        with patch("src.services.gemini_service.genai.GenerativeModel", return_value=mock_model):
            service = GeminiService(api_key="chave_teste")
            resultado = service.classificar_documento("Laudo de tomografia computadorizada.")

            assert isinstance(resultado, ClassificacaoDocumento)
            assert resultado.tipo_documento == TipoDocumentoEnum.LAUDO_EXAME_IMAGEM
            assert "Radiologia" in resultado.especialidade
            assert resultado.nivel_prioridade == NivelPrioridadeEnum.URGENTE
            assert resultado.score_confianca_classificacao == 0.98
            mock_model.generate_content.assert_called_once()

    def test_extracao_sucesso_com_entidades_completas(self):
        """Verifica a extração estruturada de entidades (Paciente, Médico, CID-10, Medicamentos)."""
        payload_mock = {
            "paciente": {"nome": "João da Silva", "idade": 54, "cpf": "123.456.789-00"},
            "medico_solicitante": {"nome": "Dr. Roberto Alves", "crm": "12345-SP"},
            "exame_ou_procedimento": "Angiotomografia de Tórax",
            "diagnostico_principal": "Tromboembolismo Pulmonar Agudo",
            "cid_extraido": "I26.9",
            "medicamentos": [{"nome": "Enoxaparina", "dosagem": "80mg", "frequencia": "12/12h"}],
            "exames_laboratoriais": [
                {
                    "analito": "D-Dímero",
                    "valor_medido": "2800",
                    "unidade": "ng/mL",
                    "referencia_impressa": "< 500",
                    "alterado": True,
                }
            ],
            "score_confianca_extracao": 0.96,
        }

        mock_response = MagicMock()
        mock_response.text = json.dumps(payload_mock)

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        with patch("src.services.gemini_service.genai.GenerativeModel", return_value=mock_model):
            service = GeminiService(api_key="chave_teste")
            resultado = service.extrair_dados_clinicos("Texto do laudo com achado crítico.")

            assert isinstance(resultado, DadosClinicosExtraidos)
            assert resultado.paciente.nome == "João da Silva"
            assert resultado.paciente.idade == 54
            assert resultado.medico_solicitante.nome == "Dr. Roberto Alves"
            assert resultado.cid_extraido == "I26.9"
            assert len(resultado.medicamentos) == 1
            assert resultado.medicamentos[0].nome == "Enoxaparina"
            assert len(resultado.exames_laboratoriais) == 1
            assert resultado.exames_laboratoriais[0].alterado is True
            assert resultado.score_confianca_extracao == 0.96

    def test_fallback_classificacao_quando_chave_ou_sdk_ausente(self):
        """Verifica se o fail-safe gera score 0.0 e NAO_IDENTIFICADO sem chave."""
        service = GeminiService(api_key="")
        # Força api_key como None
        service.api_key = None
        resultado = service.classificar_documento("Qualquer texto")

        assert isinstance(resultado, ClassificacaoDocumento)
        assert resultado.tipo_documento == TipoDocumentoEnum.NAO_IDENTIFICADO
        assert resultado.nivel_prioridade == NivelPrioridadeEnum.NAO_IDENTIFICADA
        assert resultado.score_confianca_classificacao == 0.0

    def test_fallback_extracao_quando_chave_ou_sdk_ausente(self):
        """Verifica se o fail-safe gera diagnóstico de falha e score 0.0 sem chave."""
        service = GeminiService(api_key="")
        service.api_key = None
        resultado = service.extrair_dados_clinicos("Qualquer texto")

        assert isinstance(resultado, DadosClinicosExtraidos)
        assert resultado.score_confianca_extracao == 0.0
        assert resultado.cid_extraido is None
        assert "Falha de comunicação" in (resultado.diagnostico_principal or "")

    def test_fallback_quando_api_estoura_timeout_ou_lanca_excecao(self):
        """Verifica se timeout na API aciona o fallback seguro sem lançar erro 500."""
        mock_model = MagicMock()
        mock_model.generate_content.side_effect = TimeoutError("Request timed out after 15s")

        with patch("src.services.gemini_service.genai.GenerativeModel", return_value=mock_model):
            service = GeminiService(api_key="chave_teste")
            resultado_classif = service.classificar_documento("Texto de teste")
            resultado_extrac = service.extrair_dados_clinicos("Texto de teste")

            assert resultado_classif.tipo_documento == TipoDocumentoEnum.NAO_IDENTIFICADO
            assert resultado_classif.score_confianca_classificacao == 0.0
            assert resultado_extrac.score_confianca_extracao == 0.0

    def test_fallback_quando_retorno_json_e_invalido(self):
        """Verifica resiliência quando o LLM devolve payload fora do formato Pydantic."""
        mock_response = MagicMock()
        mock_response.text = "ISSO_NAO_E_UM_JSON_VALIDO {]["

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        with patch("src.services.gemini_service.genai.GenerativeModel", return_value=mock_model):
            service = GeminiService(api_key="chave_teste")
            resultado = service.classificar_documento("Texto qualquer")

            assert resultado.tipo_documento == TipoDocumentoEnum.NAO_IDENTIFICADO
            assert resultado.score_confianca_classificacao == 0.0

    def test_tentativa_com_modelo_secundario_em_caso_de_falha_do_primeiro(self):
        """Verifica se o segundo modelo candidato (gemini-3.5-flash-lite) é acionado se o primeiro falhar."""
        payload_mock = {
            "tipo_documento": "RECEITUARIO_MEDICO",
            "especialidade": "Clínica Médica",
            "nivel_prioridade": "Rotina",
            "score_confianca_classificacao": 0.92,
        }
        mock_response = MagicMock()
        mock_response.text = json.dumps(payload_mock)

        def mock_generative_model(model_name, **kwargs):
            m = MagicMock()
            if model_name == "gemini-3.8-flash":
                m.generate_content.side_effect = Exception("Erro temporário no gemini-3.8-flash")
            else:
                m.generate_content.return_value = mock_response
            return m

        with patch("src.services.gemini_service.genai.GenerativeModel", side_effect=mock_generative_model):
            service = GeminiService(api_key="chave_teste", model_name="gemini-3.8-flash")
            resultado = service.classificar_documento("Amoxicilina 500mg 8/8h por 7 dias")

            assert resultado.tipo_documento == TipoDocumentoEnum.RECEITUARIO_MEDICO
            assert resultado.nivel_prioridade == NivelPrioridadeEnum.ROTINA
            assert resultado.score_confianca_classificacao == 0.92

    def test_classificacao_multimodal_com_bytes_de_imagem(self):
        """Verifica se a classificação aceita imagem binária (conteudo_bytes) e monta partes multimodais."""
        payload_mock = {
            "tipo_documento": "ATESTADO_MEDICO",
            "especialidade": "Clínica Geral",
            "nivel_prioridade": "Rotina",
            "score_confianca_classificacao": 0.97,
        }
        mock_response = MagicMock()
        mock_response.text = json.dumps(payload_mock)

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        with patch("src.services.gemini_service.genai.GenerativeModel", return_value=mock_model):
            service = GeminiService(api_key="chave_teste")
            bytes_imagem = b"\xff\xd8\xff\xe0\x00\x10JFIF"  # Magic bytes JPG
            resultado = service.classificar_documento(
                conteudo_texto="",
                conteudo_bytes=bytes_imagem,
                mime_type="image/jpeg"
            )

            assert resultado.tipo_documento == TipoDocumentoEnum.ATESTADO_MEDICO
            assert resultado.score_confianca_classificacao == 0.97
            
            # Garante que generate_content foi chamado com a parte de imagem
            chamada_args = mock_model.generate_content.call_args[0][0]
            assert isinstance(chamada_args, list)
            assert any(isinstance(p, dict) and p.get("mime_type") == "image/jpeg" for p in chamada_args)

    def test_documento_vazio_sem_texto_nem_bytes_aciona_fallback_imediato(self):
        """Verifica que documento completamente vazio não executa chamada na API e retorna fallback seguro."""
        with patch("src.services.gemini_service.genai.GenerativeModel") as mock_gen_model:
            service = GeminiService(api_key="chave_teste")
            resultado_classif = service.classificar_documento(conteudo_texto="", conteudo_bytes=None)
            resultado_extrac = service.extrair_dados_clinicos(conteudo_texto="   ", conteudo_bytes=None)

            assert resultado_classif.tipo_documento == TipoDocumentoEnum.NAO_IDENTIFICADO
            assert resultado_extrac.score_confianca_extracao == 0.0
            # Nenhuma chamada à API foi gasta desnecessariamente
            mock_gen_model.assert_not_called()

