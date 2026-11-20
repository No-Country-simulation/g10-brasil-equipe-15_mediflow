#!/usr/bin/env bash
# ==============================================================================
# MediFlow — Script de Automação de Deploy na Oracle Cloud Infrastructure (OCI)
# Suporta: Ubuntu 22.04 / 24.04 LTS (x86_64 e ARM64 Ampere A1 Always Free)
# ==============================================================================

set -e

ROXO='\033[0;35m'
VERDE='\033[0;32m'
AMARELO='\033[1;33m'
VERMELHO='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${ROXO}==================================================================${NC}"
echo -e "${ROXO}      🏥 MediFlow — Implantação Automatizada na Oracle Cloud      ${NC}"
echo -e "${ROXO}==================================================================${NC}"

# 1. Determina diretório raiz do projeto
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

# 2. Verifica existência do arquivo .env
if [ ! -f "${PROJECT_ROOT}/.env" ]; then
    echo -e "${VERMELHO}[ERRO] Arquivo .env não encontrado na raiz do projeto!${NC}"
    echo -e "${AMARELO}Por favor, copie o modelo e preencha suas variáveis antes do deploy:${NC}"
    echo -e "  cp .env.example .env"
    echo -e "  nano .env"
    exit 1
fi
echo -e "${VERDE}[OK] Arquivo .env detectado.${NC}"

# 2.1 Verifica existência da chave privada OCI (.pem) para montagem segura no container
OCI_KEY_HOST="${OCI_KEY_HOST_PATH:-${PROJECT_ROOT}/oci_api_key.pem}"
if [ ! -f "${OCI_KEY_HOST}" ]; then
    echo -e "${VERMELHO}[ERRO] Chave privada OCI não encontrada em: ${OCI_KEY_HOST}${NC}"
    echo -e "${AMARELO}Envie a chave .pem do bucket do grupo para a raiz do projeto como 'oci_api_key.pem' (chmod 600)${NC}"
    echo -e "${AMARELO}ou defina OCI_KEY_HOST_PATH=/caminho/para/chave.pem antes de executar este script.${NC}"
    exit 1
fi
chmod 600 "${OCI_KEY_HOST}" || true
echo -e "${VERDE}[OK] Chave privada OCI detectada (${OCI_KEY_HOST}).${NC}"

# 3. Instalação do Docker e Docker Compose (se não existirem)
if ! command -v docker &> /dev/null; then
    echo -e "${AMARELO}[INFO] Docker não encontrado. Instalando Docker Engine...${NC}"
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl gnupg lsb-release

    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg --yes

    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Permite executar docker sem sudo para o usuário atual (efeito completo em novo login)
    sudo systemctl enable --now docker || true
    sudo usermod -aG docker "$USER"
    echo -e "${VERDE}[OK] Docker instalado com sucesso.${NC}"
else
    echo -e "${VERDE}[OK] Docker já está instalado. $(docker --version)${NC}"
fi

# 3.1 Define comando Docker operacional na sessão atual (evita erro de permissão na 1ª instalação)
if docker info >/dev/null 2>&1; then
    DOCKER_CMD=(docker)
else
    echo -e "${AMARELO}[INFO] Grupo 'docker' ainda não ativo nesta sessão; usando 'sudo -E docker' neste deploy.${NC}"
    DOCKER_CMD=(sudo -E docker)
fi

# 4. Liberação das portas no Firewall local da VM (Iptables / UFW)
echo -e "${AMARELO}[INFO] Ajustando regras do firewall local da VM para portas 80 (HTTP) e 443 (HTTPS)...${NC}"
if command -v ufw &> /dev/null; then
    sudo ufw allow 80/tcp comment 'MediFlow HTTP' || true
    sudo ufw allow 443/tcp comment 'MediFlow HTTPS' || true
fi

# Imagens oficiais da OCI costumam vir com regras de DROP estritas no iptables:
if sudo iptables -L INPUT -n --line-numbers | grep -q "dpt:80"; then
    echo -e "${VERDE}[OK] Porta 80 já permitida no iptables.${NC}"
else
    echo -e "${AMARELO}[INFO] Inserindo regra de liberação da porta 80 no iptables...${NC}"
    sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT || true
    sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT || true

    # Salva regras se iptables-persistent estiver disponível
    if command -v netfilter-persistent &> /dev/null; then
        sudo netfilter-persistent save || true
    fi
fi

# 5. Execução do Docker Compose
echo -e "${AMARELO}[INFO] Construindo imagens (React SPA + FastAPI + Streamlit) e iniciando os contêineres...${NC}"
"${DOCKER_CMD[@]}" compose -f deploy/docker-compose.yml down --remove-orphans || true
"${DOCKER_CMD[@]}" compose -f deploy/docker-compose.yml up -d --build

# 6. Verificação real de saúde dos serviços via Nginx (porta 80)
echo -e "${AMARELO}[INFO] Verificando saúde real dos serviços (até 60 segundos)...${NC}"
SAUDE_API=false
SAUDE_REACT=false
SAUDE_STREAMLIT=false

for tentativa in $(seq 1 30); do
    if curl -fsS --max-time 5 http://127.0.0.1/api/v1/health >/dev/null 2>&1; then
        SAUDE_API=true
    else
        SAUDE_API=false
    fi

    if curl -fsS --max-time 5 http://127.0.0.1/ >/dev/null 2>&1; then
        SAUDE_REACT=true
    else
        SAUDE_REACT=false
    fi

    if curl -fsS --max-time 5 http://127.0.0.1/streamlit/_stcore/health >/dev/null 2>&1; then
        SAUDE_STREAMLIT=true
    else
        SAUDE_STREAMLIT=false
    fi

    if [ "${SAUDE_API}" = true ] && [ "${SAUDE_REACT}" = true ] && [ "${SAUDE_STREAMLIT}" = true ]; then
        echo -e "${VERDE}[OK] Todos os serviços responderam com saúde (tentativa ${tentativa}/30).${NC}"
        break
    fi

    sleep 2
done

if [ "${SAUDE_API}" != true ] || [ "${SAUDE_REACT}" != true ] || [ "${SAUDE_STREAMLIT}" != true ]; then
    echo -e "${VERMELHO}[ERRO] Falha na verificação de saúde pós-deploy após 60 segundos:${NC}"
    echo -e "  - API (/api/v1/health):          ${SAUDE_API}"
    echo -e "  - Portal React (/):              ${SAUDE_REACT}"
    echo -e "  - Streamlit (/streamlit/health): ${SAUDE_STREAMLIT}"
    echo -e "\n${AMARELO}Status dos contêineres:${NC}"
    "${DOCKER_CMD[@]}" compose -f deploy/docker-compose.yml ps || true
    echo -e "\n${AMARELO}Últimos logs:${NC}"
    "${DOCKER_CMD[@]}" compose -f deploy/docker-compose.yml logs --tail=40 || true
    exit 1
fi

IP_PUBLICO=$(curl -s -m 5 ifconfig.me || curl -s -m 5 icanhazip.com || echo "<IP_PUBLICO_DA_VM>")

echo -e "\n${VERDE}==================================================================${NC}"
echo -e "${VERDE}  🎉 MediFlow implantado e validado na Oracle Cloud (OCI)!        ${NC}"
echo -e "${VERDE}==================================================================${NC}"
echo -e "Acesse os serviços pelo navegador:"
echo -e "  🌐 ${VERDE}Portal Web (React SPA):${NC}    http://${IP_PUBLICO}/"
echo -e "  📖 ${VERDE}Documentação Swagger API:${NC}  http://${IP_PUBLICO}/docs"
echo -e "  🩺 ${VERDE}Health Check REST:${NC}         http://${IP_PUBLICO}/api/v1/health"
echo -e "  🧪 ${VERDE}Bancada Streamlit (HiTL):${NC}  http://${IP_PUBLICO}/streamlit/"
echo -e "\nComandos úteis para monitoramento:"
echo -e "  ${DOCKER_CMD[*]} compose -f deploy/docker-compose.yml ps"
echo -e "  ${DOCKER_CMD[*]} compose -f deploy/docker-compose.yml logs -f"
echo -e "==================================================================\n"
