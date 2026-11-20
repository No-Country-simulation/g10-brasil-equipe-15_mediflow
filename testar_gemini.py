import os
from dotenv import load_dotenv
from src.services.gemini_service import GeminiService

# Carrega a chave de API do arquivo .env
load_dotenv()

# Inicializa o serviço de IA do MediFlow
service = GeminiService()

# Exemplo de laudo hospitalar sintético para teste
laudo_teste = """
HOSPITAL SANTA CRUZ - LAUDO DE IMAGEM
Paciente: João da Silva | Idade: 54 anos
Médico: Dr. Roberto Alves | CRM: 12345-SP
Exame: Angiotomografia de Tórax
Achados: Sinais claros de Tromboembolismo Pulmonar Agudo (TEP) em artéria lobar inferior direita.
CID-10 impresso: I26.9
"""

print("=== TESTANDO CLASSIFICAÇÃO DOCUMENTAL ===")
classificacao = service.classificar_documento(laudo_teste)
print(f"Tipo Documento: {classificacao.tipo_documento}")
print(f"Prioridade: {classificacao.nivel_prioridade}")
print(f"Score de Confiança: {classificacao.score_confianca_classificacao}")

print("\n=== TESTANDO EXTRAÇÃO ESTRUTURADA DE DADOS ===")
extracao = service.extrair_dados_clinicos(laudo_teste)
print(f"Paciente: {extracao.paciente.nome}")
print(f"Médico: {extracao.medico_solicitante.nome} (CRM: {extracao.medico_solicitante.crm})")
print(f"CID Extraído: {extracao.cid_extraido}")