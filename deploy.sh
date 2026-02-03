#!/usr/bin/env bash
set -euo pipefail

if [ ! -f .env ]; then
  echo ".env not found. Run ./setup.sh first and edit .env"
  exit 1
fi

if [ ! -f "${GOOGLE_CREDENTIALS_JSON:-}" ]; then
  echo "Service account JSON not found at GOOGLE_CREDENTIALS_JSON path in .env"
  exit 1
fi

SERVICE_USER="${1:-$USER}"

sudo tee /etc/systemd/system/request-bot.service > /dev/null <<EOF
[Unit]
Description=Request Form Telegram Bot
After=network.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=/home/${SERVICE_USER}/request-bot-pos
EnvironmentFile=/home/${SERVICE_USER}/request-bot-pos/.env
ExecStart=/home/${SERVICE_USER}/request-bot-pos/.venv/bin/python /home/${SERVICE_USER}/request-bot-pos/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable request-bot
sudo systemctl restart request-bot

echo "Service started. Check status with: sudo systemctl status request-bot"
