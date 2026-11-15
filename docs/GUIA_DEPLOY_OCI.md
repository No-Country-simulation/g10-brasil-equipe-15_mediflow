# ☁️ Guia Oficial de Implantação na Oracle Cloud Infrastructure (OCI Compute Always Free)

> **Projeto:** MediFlow — Agente Autônomo de Triagem e Roteamento Clínico  
> **Programa:** Hackathon ONE G10 — Oracle Next Education & Alura  
> **Contrato de Recursos:** 100% OCI Always Free (VM Compute Ampere A1 + Object Storage)  
> **Arquitetura de Acesso:** Porta 80 única (Streamlit em `/` e FastAPI em `/api` e `/docs`)

---

## 🎯 Visão Geral da Entrega na Nuvem

Este guia orienta o desenvolvedor passo a passo a disponibilizar o **MediFlow** em uma máquina virtual pública na nuvem da Oracle, pronta para ser demonstrada e avaliada pela banca examinadora do Hackathon.

```
                  ┌───────────────────────────────────────────────┐
                  │          Oracle Cloud Always Free             │
                  │                                               │
Internet          │  ┌────────────┐   :8000   ┌────────────────┐  │
(Banca / Usuários)├─►│   Nginx    ├──────────►│  FastAPI REST  │  │
 (Porta 80 HTTP)  │  │   Proxy    │           │  (/api, /docs) │  │
                  │  │  Reverso   │   :8501   └───────┬────────┘  │
                  │  │            ├──────────┐        │           │
                  │  └────────────┘          ▼        ▼           │
                  │                   ┌──────────────┐│           │
                  │                   │  Streamlit   ││ (Backup   │
                  │                   │  Dashboard   ││  e Sync)  │
                  │                   └──────────────┘│           │
                  │                                   ▼           │
                  │                        ┌────────────────────┐ │
                  │                        │ OCI Object Storage │ │
                  │                        │  (/recebidos, etc) │ │
                  │                        └────────────────────┘ │
                  └───────────────────────────────────────────────┘
```

---

## 📋 Pré-Requisitos

1. Conta ativa no programa **Oracle Cloud Always Free**.
2. Par de chaves SSH (gerado no seu computador via `ssh-keygen` ou gerado automaticamente pelo console da OCI ao criar a VM).
3. Chaves e variáveis configuradas no seu arquivo `.env` (incluindo `GEMINI_API_KEY` e dados da OCI).

---

## 🚀 Passo 1: Criar a Máquina Virtual na OCI (Console Web)

1. Acesse o console da Oracle Cloud e vá em **Menu de Hambúrguer ☰ ➔ Compute (Recursos de Computação) ➔ Instances (Instâncias)**.
2. Clique no botão **Create Instance (Criar Instância)**.
3. Preencha as configurações recomendadas:
   - **Name (Nome):** `mediflow-production`
   - **Placement (Posicionamento):** Deixe o domínio de disponibilidade padrão.
   - **Image and Shape (Imagem e Forma):**
     - Clique em **Change Image** e selecione **Canonical Ubuntu** (versão 22.04 ou 24.04 Minimal/Server).
     - Clique em **Change Shape**, selecione **Ampere (ARM Processor)**:
       - Shape: `VM.Standard.A1.Flex`
       - OCPUs: `2` a `4` (Always Free permite até 4 OCPUs)
       - Memória RAM: `12` a `24 GB` (Always Free permite até 24 GB)
   - **Networking (Rede):**
     - Selecione sua VCN existente (ou deixe criar uma nova).
     - Subnet pública.
     - Certifique-se de marcar: **Assign a public IPv4 address (Atribuir endereço IPv4 público)**.
   - **Add SSH keys (Chaves SSH):**
     - Selecione *Paste public keys* e cole sua chave pública (`id_rsa.pub` ou `id_ed25519.pub`), ou clique em *Save private key* caso escolha gerar uma nova.
4. Clique em **Create (Criar)** e aguarde a instância mudar para o status **Running (Verde)**. Anote o **Public IP Address (IP Público)** da VM.

---

## 🔓 Passo 2: Liberar a Porta 80 na Security List da VCN

Por padrão, a OCI só permite conexões SSH (porta 22). É necessário autorizar o tráfego HTTP na porta 80:

1. Na página de detalhes da sua instância, clique no link da **Subnet (Sub-rede Pública)**.
2. Clique na **Default Security List for...**.
3. Em **Ingress Rules (Regras de Entrada)**, clique em **Add Ingress Rules**:
   - **Source Type:** CIDR
   - **Source CIDR:** `0.0.0.0/0` (qualquer endereço de internet)
   - **IP Protocol:** TCP
   - **Destination Port Range:** `80,443`
   - **Description:** `Acesso HTTP/HTTPS público MediFlow`
4. Clique em **Add Ingress Rules**.

---

## 🔑 Passo 3: Enviar as Credenciais (.env e Chave OCI) para a VM

Abra o terminal PowerShell na sua máquina local e envie com segurança os arquivos necessários para a VM via `scp`:

```powershell
# Exemplo de comando no seu computador local:
# Substitua <CAMINHO_SUA_CHAVE_SSH> e <IP_PUBLICO_DA_VM>

# 1. Enviar o arquivo .env
scp -i ~/.ssh/sua_chave_ssh .env ubuntu@<IP_PUBLICO_DA_VM>:~/.env

# 2. Enviar a chave privada da OCI (se estiver usando chave .pem no projeto)
scp -i ~/.ssh/sua_chave_ssh ./oci_api_key.pem ubuntu@<IP_PUBLICO_DA_VM>:~/oci_api_key.pem
```

---

## 🛠️ Passo 4: Conectar na VM e Executar o Deploy Automatizado

1. Conecte-se na sua máquina virtual via SSH:
   ```bash
   ssh -i ~/.ssh/sua_chave_ssh ubuntu@<IP_PUBLICO_DA_VM>
   ```

2. Clone o repositório oficial do MediFlow na VM:
   ```bash
   git clone https://github.com/No-Country-simulation/g10-brasil-equipe-15_mediflow.git
   cd g10-brasil-equipe-15_mediflow
   ```

3. Mova os arquivos de credenciais enviados para o projeto:
   ```bash
   mv ~/.env .env
   # Se enviou a chave .pem:
   mv ~/oci_api_key.pem ./oci_api_key.pem
   chmod 600 oci_api_key.pem
   ```

4. Dê permissão de execução e rode o script de implantação automatizada:
   ```bash
   chmod +x deploy/deploy_oci.sh
   ./deploy/deploy_oci.sh
   ```

O script irá automaticamente:
- Instalar Docker Engine e Docker Compose (se necessário).
- Liberar as portas 80 e 443 no firewall local do Linux (`iptables`/`ufw`).
- Construir a imagem da aplicação.
- Iniciar os contêineres em segundo plano com reinicialização automática (`restart: unless-stopped`).

---

## 🌐 Passo 5: Como Demonstrar para a Banca Avaliadora

Com o deploy finalizado, você tem um ambiente profissional pronto para a apresentação do Pitch:

| Serviço | URL de Acesso Público | Para que serve na Demonstração |
| :--- | :--- | :--- |
| **Painel Streamlit** | `http://<IP_PUBLICO>/` | Demonstração visual interativa, upload de documentos, gráficos e auditoria médica. |
| **Swagger OpenAPI** | `http://<IP_PUBLICO>/docs` | Comprovação técnica para os avaliadores de backend da Oracle (executar requisições assíncronas 202). |
| **Health Check REST** | `http://<IP_PUBLICO>/api/v1/health` | Prova de vitalidade e monitoramento dos serviços. |

---

## 🔍 Diagnóstico e Comandos Úteis na VM

Se precisar verificar logs ou status da aplicação conectada via SSH:

```bash
# Ver status dos contêineres
docker compose -f deploy/docker-compose.yml ps

# Ver logs em tempo real
docker compose -f deploy/docker-compose.yml logs -f

# Reiniciar a stack
docker compose -f deploy/docker-compose.yml restart

# Parar a aplicação
docker compose -f deploy/docker-compose.yml down
```

---

## 🛡️ Segurança e LGPD (RNF-08)

- A aplicação na OCI opera exclusivamente com dados sintéticos e fictícios.
- As credenciais `.env` e arquivos `.pem` residem na VM e **nunca** são enviados para o repositório Git.
