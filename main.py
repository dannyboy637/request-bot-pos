import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
import csv
import io
from pathlib import Path

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import gspread
from google.oauth2.service_account import Credentials


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def _load_dotenv():
    env_path = Path(__file__).with_name(".env")
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()


TIMEZONE = ZoneInfo(os.getenv("TZ", "Asia/Manila"))
NOTIFY_USERNAMES = [u.strip().lstrip("@") for u in os.getenv("NOTIFY_USERNAMES", "").split(",") if u.strip()]
ADMIN_USERNAMES = [u.strip().lstrip("@") for u in os.getenv("ADMIN_USERNAMES", "").split(",") if u.strip()]
SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "").strip()
SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Requests").strip()
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()

PLATFORMS = [
    "Facebook",
    "Instagram",
    "YouTube",
    "Brand's Website",
    "Lazada",
    "Shopee",
    "TikTok",
    "Others",
]

(
    CHOOSING_ACTION,
    BRAND_NAME,
    CREATOR_NAME,
    ROOM_NO,
    DATE_TO_BE_AIRED,
    CAMERA_REQ,
    STAGE_DESIGN,
    OTHER_TECH,
    PLATFORM_MODE,
    PLATFORM_SELECT,
    PLATFORM_OTHER,
    CONFIRM_SUBMIT,
    RECALL_MENU,
    SEARCH_BRAND,
    EXPORT_CHOICE,
    EXPORT_DATE_START,
    EXPORT_DATE_END,
    EXPORT_REQUESTER,
) = range(18)


def _get_gspread_client():
    if not GOOGLE_CREDENTIALS_JSON:
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON env var is required")
    if not SHEET_ID:
        raise RuntimeError("GOOGLE_SHEET_ID env var is required")

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_JSON, scopes=scopes)
    return gspread.authorize(creds)


def _get_sheet():
    client = _get_gspread_client()
    sheet = client.open_by_key(SHEET_ID)
    try:
        return sheet.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        return sheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=20)


def _ensure_headers(ws):
    headers = [
        "Timestamp",
        "Requester Username",
        "Brand Name",
        "Creator Name",
        "Room No / Room Letter",
        "Date to be Aired",
        "Camera Requirements",
        "Stage Design",
        "Other Technical Requirements",
        "Platform Mode",
        "Platforms",
        "Other Platforms",
    ]
    existing = ws.row_values(1)
    if existing != headers:
        ws.update("A1", [headers])


def _append_row(data):
    ws = _get_sheet()
    _ensure_headers(ws)
    ws.append_row(data, value_input_option="USER_ENTERED")


def _format_summary(user_data):
    platforms = ", ".join(user_data.get("platforms", []))
    other_platforms = user_data.get("platforms_other", "").strip()
    return (
        f"Brand Name: {user_data.get('brand_name', '')}\n"
        f"Creator Name: {user_data.get('creator_name', '')}\n"
        f"Room No / Room Letter: {user_data.get('room_no', '')}\n"
        f"Date to be Aired: {user_data.get('date_to_be_aired', '')}\n"
        f"Camera Requirements: {user_data.get('camera_requirements', '')}\n"
        f"Stage Design: {user_data.get('stage_design', '')}\n"
        f"Other Technical Requirements: {user_data.get('other_technical', '')}\n"
        f"Platform Mode: {user_data.get('platform_mode', '')}\n"
        f"Platforms: {platforms}\n"
        f"Other Platforms: {other_platforms if other_platforms else 'N/A'}"
    )


def _action_keyboard(is_admin: bool):
    buttons = [
        [InlineKeyboardButton("New Request", callback_data="action:new")],
        [InlineKeyboardButton("Recall Submissions", callback_data="action:recall")],
    ]
    if is_admin:
        buttons.append([InlineKeyboardButton("Export CSV", callback_data="action:export")])
        buttons.append([InlineKeyboardButton("Dashboard Link", callback_data="action:dashboard")])
        buttons.append([InlineKeyboardButton("Manager View", callback_data="action:manager")])
    return InlineKeyboardMarkup(buttons)


def _platform_mode_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Single Platform", callback_data="mode:single")],
        [InlineKeyboardButton("Multistreaming", callback_data="mode:multi")],
    ])


def _platforms_keyboard(selected):
    buttons = []
    for name in PLATFORMS:
        is_selected = name in selected
        label = f"{'[x]' if is_selected else '[ ]'} {name}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"platform:{name}")])
    buttons.append([InlineKeyboardButton("Done", callback_data="platform:done")])
    return InlineKeyboardMarkup(buttons)


def _is_admin(user) -> bool:
    username = (user.username or "").strip()
    if not username:
        return False
    return username.lstrip("@") in ADMIN_USERNAMES


def _parse_date(value: str):
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_admin = _is_admin(update.effective_user)
    await update.message.reply_text(
        "Hi! I can record a new request or recall past submissions. Choose an option:",
        reply_markup=_action_keyboard(is_admin),
    )
    return ConversationHandler.END


async def action_new_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Brand Name:")
    return BRAND_NAME


async def action_recall_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    logger.info("action_recall_entry triggered")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Last 10 submissions", callback_data="recall:history")],
        [InlineKeyboardButton("Search by Brand Name", callback_data="recall:search")],
    ])
    await query.message.reply_text("How would you like to recall submissions?", reply_markup=keyboard)
    return RECALL_MENU


async def recall_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "recall:history":
        return await show_history(query, context)
    if query.data == "recall:search":
        await query.edit_message_text("Enter the Brand Name to search:")
        return SEARCH_BRAND
    await query.edit_message_text("Sorry, I didn't understand that recall option. Use /menu to try again.")
    return ConversationHandler.END


async def action_export_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    logger.info("action_export_entry triggered")
    if not _is_admin(query.from_user):
        await query.message.reply_text("Sorry, only admins can export CSV.")
        return ConversationHandler.END
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("All submissions", callback_data="export:all")],
        [InlineKeyboardButton("Date range", callback_data="export:date")],
        [InlineKeyboardButton("By requester", callback_data="export:requester")],
    ])
    await query.message.reply_text("Choose an export option:", reply_markup=keyboard)
    return EXPORT_CHOICE


async def action_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _is_admin(query.from_user):
        await query.message.reply_text("Sorry, only admins can access the dashboard link.")
        return
    await query.message.reply_text(f"Dashboard link:\nhttps://docs.google.com/spreadsheets/d/{SHEET_ID}")


async def action_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _is_admin(query.from_user):
        await query.message.reply_text("Sorry, only admins can access the manager view.")
        return
    await query.message.reply_text("Preparing manager view...")
    await send_manager_view(query.message.chat_id, context)




async def brand_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["brand_name"] = update.message.text.strip()
    await update.message.reply_text("Creator Name:")
    return CREATOR_NAME


async def creator_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["creator_name"] = update.message.text.strip()
    await update.message.reply_text("Room No / Room Letter:")
    return ROOM_NO


async def room_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["room_no"] = update.message.text.strip()
    await update.message.reply_text("Date to be Aired (e.g., 2026-02-15):")
    return DATE_TO_BE_AIRED


async def date_to_be_aired(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["date_to_be_aired"] = update.message.text.strip()
    await update.message.reply_text("Camera Requirements:")
    return CAMERA_REQ


async def camera_requirements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["camera_requirements"] = update.message.text.strip()
    await update.message.reply_text("Stage Design:")
    return STAGE_DESIGN


async def stage_design(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["stage_design"] = update.message.text.strip()
    await update.message.reply_text("Other Technical Requirements:")
    return OTHER_TECH


async def other_technical(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["other_technical"] = update.message.text.strip()
    await update.message.reply_text("Platform to be used:", reply_markup=_platform_mode_keyboard())
    return PLATFORM_MODE


async def platform_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mode = "Single" if query.data == "mode:single" else "Multi"
    context.user_data["platform_mode"] = mode
    context.user_data["platforms"] = []
    await query.edit_message_text("Select platform(s):", reply_markup=_platforms_keyboard(set()))
    return PLATFORM_SELECT


async def platform_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    selection = query.data.split(":", 1)[1]

    selected = set(context.user_data.get("platforms", []))
    mode = context.user_data.get("platform_mode", "Multi")

    if selection == "done":
        context.user_data["platforms"] = list(selected)
        if "Others" in selected:
            await query.edit_message_text("Please specify other platforms:")
            return PLATFORM_OTHER
        await query.edit_message_text("Please confirm your submission:\n\n" + _format_summary(context.user_data), reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Confirm", callback_data="confirm:yes")],
            [InlineKeyboardButton("Cancel", callback_data="confirm:no")],
        ]))
        return CONFIRM_SUBMIT

    if mode == "Single":
        selected = {selection}
    else:
        if selection in selected:
            selected.remove(selection)
        else:
            selected.add(selection)

    context.user_data["platforms"] = list(selected)
    await query.edit_message_reply_markup(reply_markup=_platforms_keyboard(selected))
    return PLATFORM_SELECT


async def platform_other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["platforms_other"] = update.message.text.strip()
    await update.message.reply_text("Please confirm your submission:\n\n" + _format_summary(context.user_data), reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("Confirm", callback_data="confirm:yes")],
        [InlineKeyboardButton("Cancel", callback_data="confirm:no")],
    ]))
    return CONFIRM_SUBMIT


async def confirm_submit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "confirm:no":
        await query.edit_message_text("Submission canceled. Use /start to begin again.")
        return ConversationHandler.END

    user = query.from_user
    username = (user.username or "").strip() or f"id:{user.id}"
    timestamp = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")

    row = [
        timestamp,
        username,
        context.user_data.get("brand_name", ""),
        context.user_data.get("creator_name", ""),
        context.user_data.get("room_no", ""),
        context.user_data.get("date_to_be_aired", ""),
        context.user_data.get("camera_requirements", ""),
        context.user_data.get("stage_design", ""),
        context.user_data.get("other_technical", ""),
        context.user_data.get("platform_mode", ""),
        ", ".join(context.user_data.get("platforms", [])),
        context.user_data.get("platforms_other", ""),
    ]

    try:
        _append_row(row)
    except Exception as exc:
        logger.exception("Failed to append row")
        await query.edit_message_text(f"Sorry, I couldn't save your request. Error: {exc}")
        return ConversationHandler.END

    summary = _format_summary(context.user_data)
    await query.edit_message_text("Your request has been recorded.\n\n" + summary)

    # Notify requester and IT managers
    notify_text = (
        "New request submitted:\n\n"
        + summary
        + f"\n\nSubmitted by: @{username}"
        + f"\nTimestamp: {timestamp}"
    )

    await context.bot.send_message(chat_id=query.message.chat_id, text=notify_text)
    for uname in NOTIFY_USERNAMES:
        if uname:
            try:
                await context.bot.send_message(chat_id=f"@{uname}", text=notify_text)
            except Exception:
                logger.exception("Failed to notify %s", uname)

    context.user_data.clear()
    return ConversationHandler.END


async def show_history(query, context: ContextTypes.DEFAULT_TYPE):
    user = query.from_user
    username = (user.username or "").strip()
    if not username:
        await query.edit_message_text("I couldn't find your username. Please set a Telegram username and try again.")
        return ConversationHandler.END

    try:
        ws = _get_sheet()
        records = ws.get_all_records()
    except Exception as exc:
        logger.exception("Failed to fetch history")
        await query.edit_message_text(f"Sorry, I couldn't access the sheet. Error: {exc}")
        return ConversationHandler.END

    matches = [r for r in records if str(r.get("Requester Username", "")).strip() == username]
    latest = matches[-10:]
    if not latest:
        await query.edit_message_text("No submissions found for your username.")
        return ConversationHandler.END

    lines = []
    for r in latest:
        lines.append(
            f"- {r.get('Timestamp', '')} | {r.get('Brand Name', '')} | {r.get('Date to be Aired', '')}"
        )
    await query.edit_message_text("Your last submissions:\n" + "\n".join(lines))
    return ConversationHandler.END


async def search_brand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text.strip().lower()
    try:
        ws = _get_sheet()
        records = ws.get_all_records()
    except Exception as exc:
        logger.exception("Failed to search")
        await update.message.reply_text(f"Sorry, I couldn't access the sheet. Error: {exc}")
        return ConversationHandler.END

    matches = [r for r in records if query_text in str(r.get("Brand Name", "")).lower()]
    if not matches:
        await update.message.reply_text("No submissions found for that brand name.")
        return ConversationHandler.END

    lines = []
    for r in matches[-10:]:
        lines.append(
            f"- {r.get('Timestamp', '')} | {r.get('Brand Name', '')} | {r.get('Requester Username', '')}"
        )
    await update.message.reply_text("Matches:\n" + "\n".join(lines))
    return ConversationHandler.END


async def export_csv_records(records, chat_id, context: ContextTypes.DEFAULT_TYPE):
    if not records:
        await context.bot.send_message(chat_id=chat_id, text="No submissions found to export.")
        return

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=records[0].keys())
    writer.writeheader()
    writer.writerows(records)
    output.seek(0)

    filename = f"request-submissions-{datetime.now(TIMEZONE).strftime('%Y%m%d-%H%M%S')}.csv"
    await context.bot.send_document(chat_id=chat_id, document=output.getvalue().encode("utf-8"), filename=filename)


async def export_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":", 1)[1]
    if choice == "all":
        await query.edit_message_text("Preparing CSV export...")
        try:
            ws = _get_sheet()
            records = ws.get_all_records()
        except Exception as exc:
            logger.exception("Failed to export CSV")
            await query.message.reply_text(f"Sorry, I couldn't access the sheet. Error: {exc}")
            return ConversationHandler.END
        await export_csv_records(records, query.message.chat_id, context)
        return ConversationHandler.END
    if choice == "date":
        await query.edit_message_text("Enter start date (YYYY-MM-DD):")
        return EXPORT_DATE_START
    if choice == "requester":
        await query.edit_message_text("Enter requester username (without @):")
        return EXPORT_REQUESTER


async def export_date_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        start = _parse_date(update.message.text)
    except Exception:
        await update.message.reply_text("Invalid date format. Please enter start date as YYYY-MM-DD:")
        return EXPORT_DATE_START
    context.user_data["export_start"] = start
    await update.message.reply_text("Enter end date (YYYY-MM-DD):")
    return EXPORT_DATE_END


async def export_date_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        end = _parse_date(update.message.text)
    except Exception:
        await update.message.reply_text("Invalid date format. Please enter end date as YYYY-MM-DD:")
        return EXPORT_DATE_END

    start = context.user_data.get("export_start")
    if start and end < start:
        await update.message.reply_text("End date must be after start date. Enter end date (YYYY-MM-DD):")
        return EXPORT_DATE_END

    try:
        ws = _get_sheet()
        records = ws.get_all_records()
    except Exception as exc:
        logger.exception("Failed to export CSV")
        await update.message.reply_text(f"Sorry, I couldn't access the sheet. Error: {exc}")
        return ConversationHandler.END

    filtered = []
    for r in records:
        ts = str(r.get("Timestamp", "")).strip()
        if not ts:
            continue
        try:
            ts_dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").date()
        except Exception:
            continue
        if start <= ts_dt <= end:
            filtered.append(r)

    await export_csv_records(filtered, update.message.chat_id, context)
    context.user_data.pop("export_start", None)
    return ConversationHandler.END


async def export_requester(update: Update, context: ContextTypes.DEFAULT_TYPE):
    requester = update.message.text.strip().lstrip("@")
    try:
        ws = _get_sheet()
        records = ws.get_all_records()
    except Exception as exc:
        logger.exception("Failed to export CSV")
        await update.message.reply_text(f"Sorry, I couldn't access the sheet. Error: {exc}")
        return ConversationHandler.END

    filtered = [r for r in records if str(r.get("Requester Username", "")).strip() == requester]
    await export_csv_records(filtered, update.message.chat_id, context)
    return ConversationHandler.END


async def export_csv_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user):
        await update.message.reply_text("Sorry, only admins can export CSV.")
        return ConversationHandler.END
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("All submissions", callback_data="export:all")],
        [InlineKeyboardButton("Date range", callback_data="export:date")],
        [InlineKeyboardButton("By requester", callback_data="export:requester")],
    ])
    await update.message.reply_text("Choose an export option:", reply_markup=keyboard)
    return EXPORT_CHOICE


async def dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user):
        await update.message.reply_text("Sorry, only admins can access the dashboard link.")
        return
    await update.message.reply_text(f"Dashboard link:\nhttps://docs.google.com/spreadsheets/d/{SHEET_ID}")


async def send_manager_view(chat_id, context: ContextTypes.DEFAULT_TYPE):
    try:
        ws = _get_sheet()
        records = ws.get_all_records()
    except Exception as exc:
        logger.exception("Failed to load manager view")
        await context.bot.send_message(chat_id=chat_id, text=f"Sorry, I couldn't access the sheet. Error: {exc}")
        return

    total = len(records)
    now = datetime.now(TIMEZONE)
    last_7 = 0
    last_30 = 0
    brand_counts = {}
    for r in records:
        brand = str(r.get("Brand Name", "")).strip() or "Unknown"
        brand_counts[brand] = brand_counts.get(brand, 0) + 1
        ts = str(r.get("Timestamp", "")).strip()
        try:
            ts_dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=TIMEZONE)
        except Exception:
            continue
        delta = now - ts_dt
        if delta.days <= 7:
            last_7 += 1
        if delta.days <= 30:
            last_30 += 1

    top_brands = sorted(brand_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_lines = [f"- {name}: {count}" for name, count in top_brands] or ["- None"]

    message = (
        "Manager View\n"
        f"Total submissions: {total}\n"
        f"Last 7 days: {last_7}\n"
        f"Last 30 days: {last_30}\n"
        "Top brands:\n"
        + "\n".join(top_lines)
    )
    await context.bot.send_message(chat_id=chat_id, text=message)


async def manager_view_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user):
        await update.message.reply_text("Sorry, only admins can access the manager view.")
        return
    await send_manager_view(update.message.chat_id, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Canceled. Use /start to begin again.")
    context.user_data.clear()
    return ConversationHandler.END


def build_app():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN env var is required")

    app = ApplicationBuilder().token(token).build()

    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(action_new_entry, pattern=r"^action:new$"),
            CallbackQueryHandler(action_recall_entry, pattern=r"^action:recall$"),
            CallbackQueryHandler(action_export_entry, pattern=r"^action:export$"),
            CommandHandler("export", export_csv_command),
        ],
        states={
            BRAND_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, brand_name)],
            CREATOR_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, creator_name)],
            ROOM_NO: [MessageHandler(filters.TEXT & ~filters.COMMAND, room_no)],
            DATE_TO_BE_AIRED: [MessageHandler(filters.TEXT & ~filters.COMMAND, date_to_be_aired)],
            CAMERA_REQ: [MessageHandler(filters.TEXT & ~filters.COMMAND, camera_requirements)],
            STAGE_DESIGN: [MessageHandler(filters.TEXT & ~filters.COMMAND, stage_design)],
            OTHER_TECH: [MessageHandler(filters.TEXT & ~filters.COMMAND, other_technical)],
            PLATFORM_MODE: [CallbackQueryHandler(platform_mode, pattern=r"^mode:")],
            PLATFORM_SELECT: [CallbackQueryHandler(platform_select, pattern=r"^platform:")],
            PLATFORM_OTHER: [MessageHandler(filters.TEXT & ~filters.COMMAND, platform_other)],
            CONFIRM_SUBMIT: [CallbackQueryHandler(confirm_submit, pattern=r"^confirm:")],
            RECALL_MENU: [CallbackQueryHandler(recall_choice, pattern=r"^recall:")],
            SEARCH_BRAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_brand)],
            EXPORT_CHOICE: [CallbackQueryHandler(export_choice, pattern=r"^export:")],
            EXPORT_DATE_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, export_date_start)],
            EXPORT_DATE_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, export_date_end)],
            EXPORT_REQUESTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, export_requester)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", menu))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(action_dashboard, pattern=r"^action:dashboard$"))
    app.add_handler(CallbackQueryHandler(action_manager, pattern=r"^action:manager$"))
    app.add_handler(CommandHandler("history", lambda u, c: u.message.reply_text("Use /menu and choose Recall Submissions.")))
    app.add_handler(CommandHandler("search", lambda u, c: u.message.reply_text("Use /menu and choose Recall Submissions.")))
    app.add_handler(CommandHandler("dashboard", dashboard_command))
    app.add_handler(CommandHandler("manager", manager_view_command))
    return app


def main():
    app = build_app()
    app.run_polling()


if __name__ == "__main__":
    main()
