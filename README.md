# Request Form Telegram Bot

A Telegram bot that records request forms to Google Sheets with a step-by-step chat flow, multi-select platforms, and recall/search of past submissions.

## What It Does
- Guided form flow
- Single vs multistreaming platform selection
- Stores submissions in Google Sheets
- Recalls last 10 submissions for the requester
- Searches submissions by brand name
- Exports submissions as CSV
- Provides a dashboard link to the Google Sheet
- Admin-only manager view summary
- Notifies the requester and IT manager(s) on submit

## Setup

### 1) Create a Telegram bot
- Talk to @BotFather and create a new bot.
- Copy the bot token.

### 2) Create a Google Sheet
- Create a Google Sheet and copy its ID from the URL.

### 3) Create a Google Service Account
- Create a service account in Google Cloud.
- Enable Google Sheets API and Google Drive API.
- Create a JSON key and download it.
- Share the Google Sheet with the service account email (editor access).

### 4) Configure environment
Copy `.env.example` to `.env` and fill in values:
- `TELEGRAM_BOT_TOKEN`
- `GOOGLE_CREDENTIALS_JSON`
- `GOOGLE_SHEET_ID`
- `GOOGLE_SHEET_NAME` (optional)
- `NOTIFY_USERNAMES` (comma-separated, no @)
- `ADMIN_USERNAMES` (comma-separated, no @)
- `TZ` (default is Asia/Manila)

### 5) Install dependencies
```
pip install -r requirements.txt
```

### 6) Run the bot
```
python main.py
```

## One-Command VM Setup
On a fresh Debian/Ubuntu VM:

1) Clone the repo and enter it:
```
git clone https://github.com/dannyboy637/request-bot-pos.git
cd request-bot-pos
```

2) Run setup (creates .env template if missing):
```
./setup.sh
```

3) Edit `.env`, upload your service account JSON, then deploy:
```
./deploy.sh
```

4) Check status:
```
sudo systemctl status request-bot
```

## Deploy on Render (Free)
Render can run this as a background worker using long-polling.

### 1) Push to GitHub
Create a repo and push this project.

### 2) Create Render service
1. Go to Render and click **New +** → **Background Worker**.
2. Connect your GitHub repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `python main.py`

### 3) Set environment variables
In Render → **Environment**, add:
- `TELEGRAM_BOT_TOKEN`
- `GOOGLE_CREDENTIALS_JSON` (upload the JSON as a Render Secret File and set this to its path)
- `GOOGLE_SHEET_ID`
- `GOOGLE_SHEET_NAME`
- `NOTIFY_USERNAMES`
- `ADMIN_USERNAMES`
- `TZ`

### Notes for Render Free Tier
- Free workers may sleep when inactive. If the worker sleeps, the bot will stop polling until it wakes up.
- For always-on behavior, use a paid plan or switch to a webhook deployment.

## Commands
- `/start` Start the request form flow or recall past submissions
- `/menu` Open the main menu
- `/export` Export CSV (menu shortcut)
- `/dashboard` Dashboard link (menu shortcut)
- `/manager` Manager view summary (admin only)
- `/cancel` Cancel the current flow

## Notes
- If a requester has no Telegram username, their Telegram user ID is recorded instead.
- The bot uses inline buttons for single vs multi platform selection and platform picking.
- Export, dashboard, and manager view are restricted to `ADMIN_USERNAMES`.

## Troubleshooting
- If you see permission errors, confirm the service account has access to the Sheet.
- If you see "GOOGLE_SHEET_ID env var is required", confirm your `.env` values.
