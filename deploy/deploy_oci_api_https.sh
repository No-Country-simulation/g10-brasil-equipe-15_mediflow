#!/usr/bin/env bash
# ==============================================================================
# MediFlow — Deploy Enxuto (API FastAPI + Caddy HTTPS) na OCI Always Free
# Indicado para VM E2.1.Micro (1 GB RAM) + Frontend React hospedado na Vercel
# ==============================================================================

set -e

ROXO='\033[0;35m'
VERDE='\033[0;32m'
AMARELO='\033[1;33m'
VERMELHO='\033[0;31m'
NC='\033[0m'

echo -e "${ROXO}==================================================================${NC}"
echo -e "${ROXO}   🏥 MediFlow — Deploy Enxuto (API + HTTPS Let's Encrypt) OCI    ${NC}"
echo -e "${ROXO}==================================================================${NC}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

# 1. Verifica .env
if [ ! -f "${PROJECT_ROOT}/.env" ]; then
    echo -e "${VERMELHO}[ERRO] Arquivo .env não encontrado na raiz do projeto!${NC}"
    exit 1
fi
echo -e "${VERDE}[OK] Arquivo .env detectado.${NC}"

# Lê API_DOMAIN e CORS_ORIGINS do .env sem expor outras chaves
API_DOMAIN_ENV="$(grep -E '^API_DOMAIN=' "${PROJECT_ROOT}/.env" | tail -n 1 | cut -d'=' -f2- | tr -d '\r' | xargs || true)"
CORS_ORIGINS_ENV="$(grep -E '^CORS_ORIGINS=' "${PROJECT_ROOT}/.env" | tail -n 1 | cut -d'=' -f2- | tr -d '\r' | xargs || true)"

if [ -z "${API_DOMAIN_ENV}" ]; then
    echo -e "${VERMELHO}[ERRO] Variável API_DOMAIN não definida no .env!${NC}"
    echo -e "${AMARELO}Adicione ao .env, por exemplo:${NC}"
    echo -e "  API_DOMAIN=168.138.147.117.sslip.io"
    exit 1
fi
export API_DOMAIN="${API_DOMAIN_ENV}"
echo -e "${VERDE}[OK] API_DOMAIN=${API_DOMAIN}${NC}"

if [ -z "${CORS_ORIGINS_ENV}" ]; then
    echo -e "${AMARELO}[AVISO] CORS_ORIGINS está vazio no .env. Para o React na Vercel chamar esta API, defina:${NC}"
    echo -e "${AMARELO}  CORS_ORIGINS=https://seu-projeto.vercel.app${NC}"
else
    echo -e "${VERDE}[OK] CORS_ORIGINS configurado.${NC}"
fi

# 2. Verifica chave privada OCI (.pem)
OCI_KEY_HOST="${OCI_KEY_HOST_PATH:-${PROJECT_ROOT}/oci_api_key.pem}"
if [ ! -f "${OCI_KEY_HOST}" ]; then
    echo -e "${VERMELHO}[ERRO] Chave privada OCI não encontrada em: ${OCI_KEY_HOST}${NC}"
    exit 1
fi
chmod 600 "${OCI_KEY_HOST}" || true
echo -e "${VERDE}[OK] Chave privada OCI detectada (${OCI_KEY_HOST}).${NC}"

# 3. Instala Docker se necessário
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
    sudo systemctl enable --now docker || true
    sudo usermod -aG docker "$USER"
    echo -e "${VERDE}[OK] Docker instalado com sucesso.${NC}"
else
    echo -e "${VERDE}[OK] Docker já está instalado. $(docker --version)${NC}"
fi

# 3.1 Garante comando Docker operacional na sessão atual
if docker info >/dev/null 2>&1; then
    DOCKER_CMD=(docker)
else
    echo -e "${AMARELO}[INFO] Grupo 'docker' ainda não ativo nesta sessão; usando 'sudo -E docker' neste deploy.${NC}"
    DOCKER_CMD=(sudo -E docker)
fi

# 4. Firewall local (portas 80 e 443 obrigatórias para Let's Encrypt e HTTPS)
echo -e "${AMARELO}[INFO] Liberando portas 80 (HTTP/ACME) e 443 (HTTPS) no firewall local...${NC}"
if command -v ufw &> /dev/null; then
    sudo ufw allow 80/tcp comment 'MediFlow HTTP ACME' || true
    sudo ufw allow 443/tcp comment 'MediFlow HTTPS' || true
fi

for PORTA in 80 443; do
    if sudo iptables -L INPUT -n --line-numbers | grep -q "dpt:${PORTA}"; then
        echo -e "${VERDE}[OK] Porta ${PORTA} já permitida no iptables.${NC}"
    else
        sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport "${PORTA}" -j ACCEPT || true
    fi
done

if command -v netfilter-persistent &> /dev/null; then
    sudo netfilter-persistent save || true
fi

# 5. Subida da stack enxuta (API + Caddy HTTPS)
echo -e "${AMARELO}[INFO] Construindo mediflow-api e iniciando Caddy HTTPS...${NC}"
"${DOCKER_CMD[@]}" compose -f deploy/docker-compose.api-https.yml down --remove-orphans || true
"${DOCKER_CMD[@]}" compose -f deploy/docker-compose.api-https.yml up -d --build

# 6. Verificação real de saúde via HTTPS público (aguarda emissão do certificado Let's Encrypt)
echo -e "${AMARELO}[INFO] Aguardando certificado HTTPS e saúde de https://${API_DOMAIN}/api/v1/health (até 90s)...${NC}"
SAUDE_HTTPS=false
for tentativa in $(seq 1 30); do
    if curl -fsS --max-time 5 "https://${API_DOMAIN}/api/v1/health" >/dev/null 2>&1; then
        SAUDE_HTTPS=true
        echo -e "${VERDE}[OK] HTTPS e API saudáveis (tentativa ${tentativa}/30).${NC}"
        break
    fi
    sleep 3
done

if [ "${SAUDE_HTTPS}" != true ]; then
    echo -e "${VERMELHO}[ERRO] https://${API_DOMAIN}/api/v1/health não respondeu após 90s.${NC}"
    echo -e "${AMARELO}Status dos contêineres:${NC}"
    "${DOCKER_CMD[@]}" compose -f deploy/docker-compose.api-https.yml ps || true
    echo -e "\n${AMARELO}Logs do Caddy (verifique se portas 80 e 443 estão liberadas na Security List da OCI):${NC}"
    "${DOCKER_CMD[@]}" compose -f deploy/docker-compose.api-https.yml logs --tail=40 mediflow-caddy || true
    echo -e "\n${AMARELO}Logs da API:${NC}"
    "${DOCKER_CMD[@]}" compose -f deploy/docker-compose.api-https.yml logs --tail=40 mediflow-api || true
    exit 1
fi

echo -e "\n${VERDE}==================================================================${NC}"
echo -e "${VERDE}  🎉 MediFlow API implantada com HTTPS na Oracle Cloud (OCI)!     ${NC}"
echo -e "${VERDE}==================================================================${NC}"
echo -e "URLs públicas (HTTPS):"
echo -e "  🩺 ${VERDE}Health Check:${NC}  https://${API_DOMAIN}/api/v1/health"
echo -e "  📖 ${VERDE}Swagger API:${NC}   https://${API_DOMAIN}/docs"
echo -e "\nConfigure na Vercel (Frontend React):"
echo -e "  VITE_API_URL=https://${API_DOMAIN}"
echo -e "  VITE_USAR_FIXTURES=false"
echo -e "\nComandos úteis:"
echo -e "  ${DOCKER_CMD[*]} compose -f deploy/docker-compose.api-https.yml ps"
echo -e "  ${DOCKER_CMD[*]} compose -f deploy/docker-compose.api-https.yml logs -f"
echo -e "==================================================================\n"
