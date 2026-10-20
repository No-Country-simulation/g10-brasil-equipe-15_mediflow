"""
MediFlow - Configurações Gerais do Projeto
Carrega variáveis de ambiente do arquivo .env
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Diretório raiz do projeto
BASE_DIR = Path(__file__).resolve().parent.parent

# Carrega o .env da raiz do projeto
load_dotenv(dotenv_path=BASE_DIR / ".env")

# Configurações de LLMs
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Configurações Oracle Cloud Infrastructure (OCI)
OCI_USER_OCID = os.getenv("OCI_USER_OCID", "")
OCI_TENANCY_OCID = os.getenv("OCI_TENANCY_OCID", "")
OCI_FINGERPRINT = os.getenv("OCI_FINGERPRINT", "")
OCI_KEY_FILE = os.getenv("OCI_KEY_FILE", "")
OCI_REGION = os.getenv("OCI_REGION", "sa-saopaulo-1")
OCI_BUCKET_NAME = os.getenv("OCI_BUCKET_NAME", "mediflow-documentos-clinicos")
OCI_NAMESPACE = os.getenv("OCI_NAMESPACE", "")

# Ambiente
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
