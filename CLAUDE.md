# CLAUDE.md

## Project Overview

Telegram bot that guides users through a step-by-step request form and records submissions to Google Sheets. Built for a content/production team to submit requests (brand, creator, room, air date, camera, stage design, platforms). Admins can export CSV, view a dashboard link, and see a manager summary.

Single-file Python app (`main.py`) using `python-telegram-bot` (v20.8) for Telegram interaction and `gspread` for Google Sheets storage. No database -- Google Sheets is the only data store.

## How to Run Locally

```bash
cp .env.example .env   # then fill in real values
pip install -r requirements.txt
python main.py
```

The bot uses long-polling (no webhook). It loads `.env` from a custom parser in `main.py` (no `python-dotenv` dependency).

## Key Files

- `main.py` -- entire bot logic: conversation handler, Google Sheets CRUD, CSV export, manager view. All 18 conversation states defined as module-level constants.
- `.env.example` -- template for required environment variables
- `requirements.txt` -- three dependencies: `python-telegram-bot`, `gspread`, `google-auth`
- `setup.sh` -- VM bootstrap: creates `.env` template, installs Python venv, pip installs deps
- `deploy.sh` -- creates and enables a systemd service (`request-bot.service`)
- `render.yaml` -- Render background worker config for free-tier deployment
- `REQUEST FORMAT.pdf` -- reference document for the form fields

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | Bot token from @BotFather |
| `GOOGLE_CREDENTIALS_JSON` | Yes | Path to Google service account JSON key file |
| `GOOGLE_SHEET_ID` | Yes | ID from the Google Sheets URL |
| `GOOGLE_SHEET_NAME` | No | Worksheet tab name (default: `Requests`) |
| `NOTIFY_USERNAMES` | No | Comma-separated Telegram usernames to notify on new submissions |
| `ADMIN_USERNAMES` | No | Comma-separated usernames with access to export, dashboard, manager view |
| `TZ` | No | Timezone for timestamps (default: `Asia/Manila`) |

## Bot Commands

- `/start` -- opens the main menu (new request, recall, admin actions)
- `/menu` -- same as `/start`
- `/export` -- CSV export with filters: all, date range, or by requester (admin only)
- `/dashboard` -- link to the Google Sheet (admin only)
- `/manager` -- summary view: total submissions, last 7/30 days, top 5 brands (admin only)
- `/cancel` -- cancels the current conversation flow

## Architecture Notes

- **Conversation flow**: uses `ConversationHandler` with 18 states (CHOOSING_ACTION through EXPORT_REQUESTER). Entry points are inline keyboard callbacks from the main menu plus the `/export` command.
- **Platform selection**: supports single-select and multi-select modes via inline keyboard toggles. If "Others" is selected, prompts for free-text input.
- **Google Sheets**: auto-creates the worksheet and ensures headers exist on every write. Uses `append_row` for submissions.
- **Notifications**: on submit, notifies the requester's chat and each username in `NOTIFY_USERNAMES` via `send_message`.
- **Admin gating**: export, dashboard, and manager commands check `_is_admin()` against `ADMIN_USERNAMES`.

## Deployment

### VM with systemd
```bash
./setup.sh    # bootstrap venv and deps
# edit .env with real credentials
./deploy.sh   # creates systemd unit, enables and starts the service
sudo systemctl status request-bot
```

### Render free tier
Push to GitHub, create a Background Worker on Render, set env vars in Render dashboard. See `render.yaml` for config. Note: free-tier workers may sleep when inactive.

## Common Tasks

- **Add a new form field**: add a new conversation state constant, create a handler function, wire it into the `ConversationHandler` states dict, update `_format_summary()` and `_append_row()`, and add the column to `_ensure_headers()`.
- **Change platform options**: edit the `PLATFORMS` list at the top of `main.py`.
- **Add a new admin command**: add a handler function, register it in `build_app()`, and gate with `_is_admin()`.
