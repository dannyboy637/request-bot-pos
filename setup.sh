#!/usr/bin/env bash
set -euo pipefail

if [ ! -f .env ]; then
  cat <<'ENV'
TELEGRAM_BOT_TOKEN=YOUR_TOKEN
GOOGLE_CREDENTIALS_JSON=/home/$USER/request-bot-pos/sa.json
GOOGLE_SHEET_ID=YOUR_SHEET_ID
GOOGLE_SHEET_NAME=Requests
NOTIFY_USERNAMES=danielpgomez
ADMIN_USERNAMES=danielpgomez
TZ=Asia/Manila
ENV
  echo "Created .env template. Please edit it before running deploy.sh."
  exit 0
fi

sudo apt update
sudo apt install -y python3-venv git

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

echo "Setup complete. Now run ./deploy.sh"
