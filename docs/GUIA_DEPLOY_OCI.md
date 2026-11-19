# ☁️ Guia Oficial de Implantação na Oracle Cloud Infrastructure (OCI Compute Always Free)

> **Projeto:** MediFlow — Agente Autônomo de Triagem e Roteamento Clínico  
> **Programa:** Hackathon ONE G10 — Oracle Next Education & Alura  
> **Contrato de Recursos:** 100% OCI Always Free (VM Compute Ampere A1 + Object Storage)  
> **Arquitetura de Acesso:** Porta 80 única — Portal React SPA em `/`, FastAPI em `/api` e `/docs`, e Bancada Streamlit em `/streamlit/`

---

## 🎯 Visão Geral da Entrega na Nuvem

Este guia orienta o desenvolvedor passo a passo a disponibilizar o **MediFlow** em uma máquina virtual pública na nuvem da Oracle, pronta para ser demonstrada e avaliada pela banca examinadora do Hackathon.

```text
                  ┌─────────────────────────────────────────────────────┐
                  │             Oracle Cloud Always Free                │
                  │                                                     │
Internet          │  ┌─────────────────┐   /     ┌───────────────────┐  │
(Banca / Usuários)├─►│     Nginx       ├────────►│  Portal React SPA │  │
 (Porta 80 HTTP)  │  │  Proxy Reverso  │         │  (estáticos dist) │  │
                  │  │   + Estáticos   │  :8000  └───────────────────┘  │
                  │  │                 ├────────►┌───────────────────┐  │
                  │  │                 │         │  FastAPI REST     │  │
                  │  │                 │         │  (--workers 1)    │  │
                  │  │                 │  :8501  │  (/api, /docs)    │  │
                  │  │                 ├────┐    └─────────┬─────────┘  │
                  │  └─────────────────┘    ▼              │            │
                  │                  ┌──────────────┐      │ (Backup    │
                  │                  │  Streamlit   │      │  e Sync)   │
                  │                  │ (/streamlit/)├──────┤            │
                  │                  └──────────────┘      ▼            │
                  │                              ┌────────────────────┐ │
                  │                              │ OCI Object Storage │ │
                  │                              │  (Bucket do Grupo) │ │
                  │                              └────────────────────┘ │
                  └─────────────────────────────────────────────────────┘
```

> [!IMPORTANT]
> **Reaproveitamento do OCI Object Storage do Grupo:** Não é obrigatório criar um novo bucket na mesma conta OCI da VM Compute. Como o `OCIStorage` autentica via API Key HTTPS (`OCI_USER_OCID`, `OCI_TENANCY_OCID`, `OCI_FINGERPRINT`, `OCI_KEY_FILE`, `OCI_NAMESPACE`, `OCI_BUCKET_NAME`), a VM pode gravar diretamente no bucket centralizado `mediflow-documentos` da conta do integrante responsável, desde que a conta e a chave permaneçam ativas durante o período da banca.

> [!NOTE]
> **Decisão D-01 (`--workers 1`):** A API mantém o índice de triagens em memória RAM durante a execução do processo. Por isso, o `docker-compose.yml` executa o Uvicorn obrigatoriamente com `--workers 1`, garantindo consistência no polling de `/status`, `/resultado` e `/historico`.

---

## 📋 Pré-Requisitos

1. Conta ativa no programa **Oracle Cloud Always Free**.
2. Par de chaves SSH (gerado via `ssh-keygen` ou baixado do console OCI ao criar a VM).
3. Arquivo `.env` com `GEMINI_API_KEY` (recomenda-se chave com cota disponível para o dia da banca) e credenciais OCI do bucket `mediflow-documentos`.
4. Chave privada da API OCI (`.pem`, ex.: `mediflow_api_key.pem`) renomeada como `oci_api_key.pem` na raiz do projeto na VM.

---

## 🚀 Passo 1: Criar a Máquina Virtual na OCI (Console Web)

1. Acesse o console da Oracle Cloud e vá em **Menu ☰ ➔ Compute ➔ Instances**.
2. Clique em **Create Instance**.
3. Configurações recomendadas:
   - **Name:** `mediflow-production`
   - **Image:** **Canonical Ubuntu** (`22.04` ou `24.04` LTS).
   - **Shape:** **Ampere (ARM64)** — `VM.Standard.A1.Flex` (`2` a `4` OCPUs, `12` a `24 GB` RAM — Always Free).
   - **Networking:** VCN com subnet pública e **Assign a public IPv4 address** marcado.
   - **Add SSH keys:** Cole sua chave pública (`id_ed25519.pub` / `id_rsa.pub`) ou salve a chave privada gerada.
4. Clique em **Create** e anote o **Public IP Address**.

---

## 🔓 Passo 2: Liberar a Porta 80 na Security List da VCN

1. Na página de detalhes da instância, clique na **Subnet Pública**.
2. Clique na **Default Security List**.
3. Em **Ingress Rules**, clique em **Add Ingress Rules**:
   - **Source Type:** CIDR · **Source CIDR:** `0.0.0.0/0`
   - **IP Protocol:** TCP · **Destination Port Range:** `80,443`
   - **Description:** `Acesso HTTP/HTTPS público MediFlow`
4. Salve a regra.

---

## 🔑 Passo 3: Enviar `.env` e Chave OCI (`.pem`) para a VM

No PowerShell da sua máquina local:

```powershell
# 1. Enviar o arquivo .env
scp -i ~/.ssh/sua_chave_ssh .env ubuntu@<IP_PUBLICO_DA_VM>:~/.env

# 2. Enviar a chave privada OCI (renomeando para oci_api_key.pem na VM)
scp -i ~/.ssh/sua_chave_ssh "C:\caminho\para\mediflow_api_key.pem" ubuntu@<IP_PUBLICO_DA_VM>:~/oci_api_key.pem
```

> [!TIP]
> Não é necessário alterar manualmente `OCI_KEY_FILE` dentro do `.env` para o container: o `deploy/docker-compose.yml` já monta `../oci_api_key.pem` em modo somente leitura em `/app/oci_api_key.pem` e sobrescreve `OCI_KEY_FILE=/app/oci_api_key.pem` nos serviços da API e do Streamlit.

---

## 🛠️ Passo 4: Conectar na VM e Executar o Deploy Automatizado (Branch `main` / Tag `v1.2.0`)

1. Conecte-se via SSH:
   ```bash
   ssh -i ~/.ssh/sua_chave_ssh ubuntu@<IP_PUBLICO_DA_VM>
   ```

2. Clone o repositório oficial na branch congelada de produção (`main` / tag `v1.2.0`):
   ```bash
   git clone --branch main https://github.com/No-Country-simulation/g10-brasil-equipe-15_mediflow.git
   cd g10-brasil-equipe-15_mediflow
   ```

3. Mova o `.env` e a chave `.pem` para a raiz do projeto:
   ```bash
   mv ~/.env .env
   mv ~/oci_api_key.pem ./oci_api_key.pem
   chmod 600 ./oci_api_key.pem
   ```

4. Execute o script automatizado de implantação:
   ```bash
   chmod +x deploy/deploy_oci.sh
   ./deploy/deploy_oci.sh
   ```

O script automaticamente:
- Valida a presença de `.env` e `oci_api_key.pem`.
- Instala Docker Engine e Docker Compose (se necessário).
- Libera as portas `80` e `443` no firewall local (`ufw`/`iptables`).
- Faz o build multi-stage do Portal React + Nginx e dos containers FastAPI e Streamlit.
- Inicia a stack em segundo plano com reinicialização automática (`restart: unless-stopped`).

---

## 🌐 Passo 5: URLs de Demonstração para a Banca Avaliadora

| Serviço | URL de Acesso Público | Uso na Apresentação |
| :--- | :--- | :--- |
| **Portal Web (React SPA)** | `http://<IP_PUBLICO>/` | Interface principal do MediFlow (Login demo: CRM `145892` · UF `SP` · Senha `mediflow`). |
| **Swagger OpenAPI** | `http://<IP_PUBLICO>/docs` | Comprovação técnica dos endpoints REST assíncronos (`202 Accepted`, status, histórico). |
| **Health Check REST** | `http://<IP_PUBLICO>/api/v1/health` | Prova de vitalidade (`api`, `langgraph` e `oci_storage` online). |
| **Bancada Streamlit (HiTL)** | `http://<IP_PUBLICO>/streamlit/` | Painel auxiliar de laboratório e auditoria médica. |

---

## 🔍 Diagnóstico e Comandos Úteis na VM

```bash
# Status e healthchecks dos contêineres
docker compose -f deploy/docker-compose.yml ps

# Logs em tempo real (todos os serviços ou apenas API)
docker compose -f deploy/docker-compose.yml logs -f
docker compose -f deploy/docker-compose.yml logs -f mediflow-api

# Atualizar para nova versão publicada na main
git pull origin main
docker compose -f deploy/docker-compose.yml up -d --build

# Parar a aplicação
docker compose -f deploy/docker-compose.yml down
```

---

## 🛡️ Segurança e LGPD (RNF-08)

- A aplicação na OCI opera exclusivamente com dados sintéticos e fictícios.
- `.env` e `oci_api_key.pem` residem apenas na VM e são bloqueados tanto no `.gitignore` quanto no `.dockerignore`.
