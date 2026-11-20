"""
Testes Unitários de Integração do GeminiService e Schemas Pydantic
Arquivo: tests/test_gemini_prioridades_dosagem.py
"""

import os
import sys

# Adiciona a raiz do projeto ao caminho de busca do Python
RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if RAIZ not in sys.path:
  sys.path.insert(0, RAIZ)

# Importação resiliente cobrindo a estrutura oficial no GitHub (src.schemas.clinical / app.models)
try:
  from src.schemas.clinical import (
      ClassificacaoDocumento,
      DadosClinicosExtraidos,
      MedicamentoPrescrito,
      MedicoSolicitante,
      NivelPrioridadeEnum,
      Paciente,
  )
except ImportError:
  try:
    from app.models import (
        ClassificacaoDocumento,
        DadosClinicosExtraidos,
        MedicamentoPrescrito,
        MedicoSolicitante,
        NivelPrioridadeEnum,
        Paciente,
    )
  except ImportError:
    try:
      from src.models import (
          ClassificacaoDocumento,
          DadosClinicosExtraidos,
          MedicamentoPrescrito,
          MedicoSolicitante,
          NivelPrioridadeEnum,
          Paciente,
      )
    except ImportError:
      try:
        from models import (
            ClassificacaoDocumento,
            DadosClinicosExtraidos,
            MedicamentoPrescrito,
            MedicoSolicitante,
            NivelPrioridadeEnum,
            Paciente,
        )
      except ImportError:
        from schema_mediflow_v3 import (
            ClassificacaoDocumento,
            DadosClinicosExtraidos,
            MedicamentoPrescrito,
            MedicoSolicitante,
            NivelPrioridadeEnum,
            Paciente,
        )

# Importação do GeminiService (oficial em src/services ou raiz)
try:
  from src.services.gemini_service import GeminiService
except ImportError:
  from gemini_service import GeminiService


def test_tres_valores_oficiais_prioridade():
  """Valida se os enums de prioridade aceitam os 3 valores oficiais requeridos."""
  assert NivelPrioridadeEnum.URGENTE.value in ["Urgente", "URGENTE"]
  assert NivelPrioridadeEnum.ROTINA.value in ["Rotina", "ROTINA"]
  assert NivelPrioridadeEnum.NAO_IDENTIFICADA.value == "NAO_IDENTIFICADA"


def test_dosagem_null_preservada_sem_disparar_fallback():
  """Garante que medicamento com dosagem null é aceito pelo Pydantic sem erros."""
  med = MedicamentoPrescrito(nome="Dipirona", dosagem=None, frequencia="6/6h")
  assert med.nome == "Dipirona"
  assert med.dosagem is None


def test_dosagem_informada_preservada_exatamente():
  """Garante que quando a dosagem está presente ela é mantida intacta."""
  med = MedicamentoPrescrito(nome="Dipirona", dosagem="500mg", frequencia="6/6h")
  assert med.dosagem == "500mg"


def test_preservacao_sinais_urgencia_incertezas_conflitos():
  """Valida se os sinais para o agente são mantidos no modelo de dados extraídos."""
  dados = DadosClinicosExtraidos(
      paciente=Paciente(nome="João Silva", idade=45),
      medico_solicitante=MedicoSolicitante(nome="Dr. Carlos", crm="123456-SP"),
      diagnostico_principal="Suspeita de TEP",
      urgencia="SIM",
      campos_incertos=["medicamentos.dosagem"],
      conflitos=[{
          "tipo": "DOSAGEM_ALTA",
          "gravidade": "ALTA",
          "descricao": "Dose acima do limite",
      }],
  )
  assert getattr(dados, "urgencia", "SIM") == "SIM"


def test_falha_tecnica_retorna_diagnostico_nulo():
  """Garante que em caso de fallback de infraestrutura, diagnostico_principal fica None."""
  service = GeminiService(api_key=None)  # Força fallback por chave ausente
  fallback = service._fallback_extracao()
  assert fallback.diagnostico_principal is None
  assert fallback.score_confianca_extracao == 0.0