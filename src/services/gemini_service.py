"""
MediFlow - Serviço de Inteligência Multimodal e Extração Clínica (Google Gemini)
Arquivo: src/services/gemini_service.py
"""

import json
import logging
import os
from typing import Any, Dict, Optional, Union
from dotenv import load_dotenv
from pydantic import ValidationError

load_dotenv()

logger = logging.getLogger("mediflow.gemini_service")
logging.basicConfig(level=logging.INFO)

try:
    import google.generativeai as genai
except ImportError:
    genai = None

# Importação direta e canônica do schema oficial do projeto
from src.schemas.clinical import (
    ClassificacaoDocumento,
    DadosClinicosExtraidos,
    ItemExameLaboratorial,
    MedicamentoPrescrito,
    MedicoSolicitante,
    NivelPrioridadeEnum,
    Paciente,
    TipoDocumentoEnum,
)

SYSTEM_INSTRUCTION_CLASSIFICACAO = """
Você é o componente especializado de Classificação Documental e Triagem do MediFlow.
Sua missão é ler documentos hospitalares e classificá-los com rigor e precisão médica estrita.

PRIORIDADES DE TRIAGEM OFICIAIS:
- URGENTE: Achados com risco iminente de morte ou lesão grave.
- ROTINA: Exames normais, receitas de uso contínuo, atestados simples ou procedimentos eletivos.
- NAO_IDENTIFICADA: Use quando a ilegibilidade ou ausência de dados impedir qualquer determinação clínica.
"""

SYSTEM_INSTRUCTION_EXTRACAO = """
Você é o componente especialista em Extração Estruturada de Entidades Médicas do MediFlow.
Sua missão é extrair dados clínicos com fidelidade absoluta ao texto do documento.
Se a dosagem do medicamento for ausente ou ilegível, preencha o campo 'dosagem' estritamente como null.
"""


class GeminiService:
    """Serviço central de integração multimodal com Google Gemini."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-1.5-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name

        if not genai:
            logger.warning("[GeminiService] SDK google-generativeai não está instalado no ambiente.")
        elif not self.api_key:
            logger.warning("[GeminiService] Chave GEMINI_API_KEY não encontrada nas variáveis de ambiente.")
        else:
            genai.configure(api_key=self.api_key)

    def classificar_documento(self, conteudo_texto: str) -> ClassificacaoDocumento:
        """Classifica o documento nas categorias e prioridades oficiais."""
        if not genai or not self.api_key:
            logger.warning("[GeminiService] Chamada redirecionada para fallback defensivo (SDK ou Chave ausente).")
            return self._fallback_classificacao("SDK ou Chave ausente")

        prompt_blindado = f"""
        Analise o documento clínico a seguir e gere a classificação estruturada correspondente:

        <documento_clinico>
        {conteudo_texto}
        </documento_clinico>
        """

        try:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=SYSTEM_INSTRUCTION_CLASSIFICACAO,
                generation_config={
                    "temperature": 0.0,
                    "response_mime_type": "application/json",
                    "response_schema": ClassificacaoDocumento,
                },
            )

            response = model.generate_content(prompt_blindado)
            resultado = ClassificacaoDocumento.model_validate_json(response.text)
            logger.info(f"[GeminiService] Classificação concluída com sucesso: {resultado.tipo_documento} | Prioridade: {resultado.nivel_prioridade}")
            return resultado

        except Exception as e:
            logger.error(f"[GeminiService] Falha na classificação via Gemini: {e}")
            return self._fallback_classificacao(str(e))

    def extrair_dados_clinicos(self, conteudo_texto: str) -> DadosClinicosExtraidos:
        """Extrai entidades médicas com saída estruturada nativa validada em DadosClinicosExtraidos."""
        if not genai or not self.api_key:
            logger.warning("[GeminiService] Extração redirecionada para fallback defensivo (SDK ou Chave ausente).")
            return self._fallback_extracao()

        prompt_blindado = f"""
        Extraia as entidades médicas do documento abaixo com fidelidade estrita.
        Atenção: Se o código CID não constar expressamente no documento, 'cid_extraido' DEVE ser null.

        <documento_clinico>
        {conteudo_texto}
        </documento_clinico>
        """

        try:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=SYSTEM_INSTRUCTION_EXTRACAO,
                generation_config={
                    "temperature": 0.0,
                    "response_mime_type": "application/json",
                    "response_schema": DadosClinicosExtraidos,
                },
            )

            response = model.generate_content(prompt_blindado)
            resultado = DadosClinicosExtraidos.model_validate_json(response.text)
            logger.info(f"[GeminiService] Extração de dados concluída: Paciente={resultado.paciente.nome or 'null'}")
            return resultado

        except Exception as e:
            logger.error(f"[GeminiService] Falha na extração de entidades: {e}")
            return self._fallback_extracao()

    def _fallback_classificacao(self, motivo: str) -> ClassificacaoDocumento:
        """Fallback defensivo em caso de erro, timeout ou indisponibilidade da API."""
        return ClassificacaoDocumento(
            tipo_documento=TipoDocumentoEnum.NAO_IDENTIFICADO,
            especialidade=None,
            nivel_prioridade=NivelPrioridadeEnum.NAO_IDENTIFICADA,
            score_confianca_classificacao=0.0,
        )

    def _fallback_extracao(self) -> DadosClinicosExtraidos:
        """Fallback defensivo para extração clínica."""
        return DadosClinicosExtraidos(
            paciente=Paciente(nome=None, idade=None, cpf=None),
            medico_solicitante=MedicoSolicitante(nome=None, crm=None),
            exame_ou_procedimento=None,
            diagnostico_principal=None,
            cid_extraido=None,
            medicamentos=[],
            exames_laboratoriais=[],
            score_confianca_extracao=0.0,
            urgencia="INDETERMINADO",
            campos_incertos=[],
            conflitos=[],
        )
