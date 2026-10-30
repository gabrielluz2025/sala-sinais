#!/bin/bash
# Bootstrap Sala de Sinais on Ubuntu VPS (financasmais.com)
# Run as root on a fresh VPS: bash bootstrap-vps-ubuntu.sh
#
# BEFORE RUNNING:
# 1. Point DNS A records @ and www to this server's public IP (remove Hostinger CDN parking).
# 2. Repo is PRIVATE — set GITHUB_TOKEN (read repo) or use SSH deploy key:
#    export GITHUB_TOKEN=ghp_xxxx
# 3. Edit DOMAIN below if needed.

set -euo pipefail
DOMAIN="${DOMAIN:-financasmais.com}"
APP_USER="${APP_USER:-sinais}"
APP_DIR="/home/${APP_USER}/sala-sinais"
REPO="https://github.com/gabrielluz2025/sala-sinais.git"

if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  REPO="https://${GITHUB_TOKEN}@github.com/gabrielluz2025/sala-sinais.git"
fi

echo "==> Packages"
apt update && apt install -y python3-venv python3-pip nginx certbot python3-certbot-nginx git

id "$APP_USER" &>/dev/null || useradd -m -s /bin/bash "$APP_USER"

if [[ ! -d "$APP_DIR/.git" ]]; then
  echo "==> Clone (private repo needs GITHUB_TOKEN or deploy key)"
  sudo -u "$APP_USER" git clone "$REPO" "$APP_DIR"
fi

cd "$APP_DIR"
sudo -u "$APP_USER" python3 -m venv .venv
sudo -u "$APP_USER" .venv/bin/pip install -r requirements.txt

if [[ ! -f .env ]]; then
  sudo -u "$APP_USER" cp .env.example .env
  echo "==> Edit $APP_DIR/.env: API_HOST=0.0.0.0, ENGINE_MODE=simulation, WEBHOOK_SECRET, CORS_ORIGINS=https://${DOMAIN}"
fi

mkdir -p data
chown -R "${APP_USER}:${APP_USER}" data

echo "==> systemd"
cp deploy/systemd/sala-sinais-api.service.example /etc/systemd/system/sala-sinais-api.service
cp deploy/systemd/sala-sinais-engine.service.example /etc/systemd/system/sala-sinais-engine.service
sed -i "s|/home/sinais/sala-sinais|${APP_DIR}|g" /etc/systemd/system/sala-sinais-*.service
systemctl daemon-reload
systemctl enable --now sala-sinais-api sala-sinais-engine

echo "==> nginx"
cp deploy/nginx-sala-sinais.conf.example /etc/nginx/sites-available/sala-sinais
sed -i "s|financasmais.com|${DOMAIN}|g" /etc/nginx/sites-available/sala-sinais
ln -sf /etc/nginx/sites-available/sala-sinais /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "==> SSL (interactive)"
certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" --non-interactive --agree-tos -m "admin@${DOMAIN}" || true

echo "==> Done. Test: curl -s http://127.0.0.1:8000/health"
echo "    Then open https://${DOMAIN}/"
