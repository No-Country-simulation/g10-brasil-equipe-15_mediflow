# MediFlow — Dockerfile de Produção Multi-Uso (FastAPI & Streamlit)
# Compatível com arquiteturas x86_64 (AMD) e aarch64 (ARM - OCI Ampere A1)

FROM python:3.11-slim

# Evita geração de bytecode .pyc e garante logs em tempo real
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Instala dependências essenciais do sistema operacional para PyMuPDF, Pillow e rede
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libgl1 \
    libglib2.0-0 \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Instala dependências do Python em camada de cache isolada
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia código-fonte e dados essenciais da aplicação
COPY src/ /app/src/
COPY data/ /app/data/
COPY pytest.ini /app/pytest.ini

# Portas de serviço expostas (8000: FastAPI REST | 8501: Streamlit Dashboard)
EXPOSE 8000 8501

# Comando padrão (pode ser sobrescrito pelo docker-compose)
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
