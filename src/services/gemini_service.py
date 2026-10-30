"""
MediFlow - Serviço de Inteligência Multimodal e Extração Clínica (Google Gemini)
Arquivo: src/services/gemini_service.py
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Union
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
Não crie categorias intermediárias. Retorne os valores exatamente como escritos acima.
"""

SYSTEM_INSTRUCTION_EXTRACAO = """
Você é o componente especialista em Extração Estruturada de Entidades Médicas do MediFlow.
Sua missão é extrair dados clínicos com fidelidade absoluta ao texto do documento.
Se a dosagem ou frequência do medicamento for ausente ou ilegível, preencha o campo 'dosagem' estritamente como null. Nunca deduza ou complete esses valores.
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

    def _montar_partes_conteudo(
        self,
        instrucao_base: str,
        conteudo_texto: str = "",
        conteudo_bytes: Optional[bytes] = None,
        mime_type: Optional[str] = None
    ) -> List[Any]:
        """Monta a lista de partes para a API multimodal do Gemini com isolamento de segurança."""
        partes: List[Any] = []
        if conteudo_bytes:
            mime = (mime_type or "image/jpeg").lower().strip()
            if mime in ["jpg", "image/jpg"]:
                mime = "image/jpeg"
            elif mime in ["png", "image/png"]:
                mime = "image/png"
            elif mime in ["webp", "image/webp"]:
                mime = "image/webp"
            elif mime in ["pdf", "application/pdf"]:
                mime = "application/pdf"
            elif "/" not in mime:
                mime = f"image/{mime}"
            partes.append({"mime_type": mime, "data": conteudo_bytes})

        if conteudo_texto and conteudo_texto.strip():
            partes.append(f"{instrucao_base}\n<documento_clinico>\n{conteudo_texto}\n</documento_clinico>")
        else:
            partes.append(f"{instrucao_base}\nDocumento em anexo. Trate o conteúdo com fidelidade estrita entre as tags <documento_clinico>.")

        return partes

    def classificar_documento(
        self,
        conteudo_texto: str = "",
        conteudo_bytes: Optional[bytes] = None,
        mime_type: Optional[str] = None
    ) -> ClassificacaoDocumento:
        """Classifica o documento nas categorias e prioridades oficiais."""
        if not genai or not self.api_key:
            logger.warning("[GeminiService] Chamada redirecionada para fallback defensivo (SDK ou Chave ausente).")
            return self._fallback_classificacao("SDK ou Chave ausente")

        if not (conteudo_texto and conteudo_texto.strip()) and not conteudo_bytes:
            return self._fallback_classificacao("Documento vazio sem texto ou bytes")

        partes = self._montar_partes_conteudo(
            instrucao_base="Analise o documento clínico e gere a classificação estruturada correspondente:",
            conteudo_texto=conteudo_texto,
            conteudo_bytes=conteudo_bytes,
            mime_type=mime_type
        )

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

            response = model.generate_content(partes)
            resultado = ClassificacaoDocumento.model_validate_json(response.text)
            logger.info(f"[GeminiService] Classificação concluída com sucesso: {resultado.tipo_documento} | Prioridade: {resultado.nivel_prioridade}")
            return resultado

        except Exception as e:
            logger.error(f"[GeminiService] Falha na classificação via Gemini: {e}")
            return self._fallback_classificacao(str(e))

    def extrair_dados_clinicos(
        self,
        conteudo_texto: str = "",
        conteudo_bytes: Optional[bytes] = None,
        mime_type: Optional[str] = None
    ) -> DadosClinicosExtraidos:
        """Extrai entidades médicas com saída estruturada nativa validada em DadosClinicosExtraidos."""
        if not genai or not self.api_key:
            logger.warning("[GeminiService] Extração redirecionada para fallback defensivo (SDK ou Chave ausente).")
            return self._fallback_extracao()

        if not (conteudo_texto and conteudo_texto.strip()) and not conteudo_bytes:
            return self._fallback_extracao()

        partes = self._montar_partes_conteudo(
            instrucao_base="Extraia as entidades médicas do documento com fidelidade estrita. Se CID não constar, 'cid_extraido' DEVE ser null.",
            conteudo_texto=conteudo_texto,
            conteudo_bytes=conteudo_bytes,
            mime_type=mime_type
        )

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

            response = model.generate_content(partes)
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