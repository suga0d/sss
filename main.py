import csv
import secrets
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =================== CONFIG ===================
TOKEN = "8532412255:AAErqUAlFsMansssdBxKo7jpiT42adw6J38"   
# ==============================================

csv_lock = Lock()
machine_status = {}
user_files = {} 

async def forwarded_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not machine_status.get(chat_id, False):
        return

    message = update.message
    user_id = update.effective_user.id

    # Only process forwarded messages
    if not message.forward_origin:
        return

    # Accept text or captions (images)
    text = message.text or message.caption
    if not text:
        return  # forward has no text → ignore

    # Process first 6 lines
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    lines = lines[:6]

    # Save to CSV
    date_str = datetime.now(timezone.utc).strftime("%m/%d/%Y")
    row = [date_str] + lines + [""] * (5 - len(lines))
    append_row(user_id, row)

    # React with ❤️
    try:
        await message.react("❤️")
    except:
        pass


# =====================================================
#                     FILE HELPERS
# =====================================================
def get_user_csv(user_id: int) -> Path:
    if user_id not in user_files:
        rand_tag = secrets.token_hex(4)
        user_files[user_id] = f"report_{user_id}_{rand_tag}.csv"
    return Path(user_files[user_id])


def ensure_csv(user_id: int):
    csv_path = get_user_csv(user_id)
    if not csv_path.exists():
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "line1", "line2", "line3", "line4", "line5"])


def clear_csv(user_id: int):
    csv_path = get_user_csv(user_id)
    if csv_path.exists():
        csv_path.unlink()
    ensure_csv(user_id)


# =====================================================
#               PARSER FOR /ID MESSAGES
# =====================================================
def parse_message(text: str):
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    lines = lines[:6]

    parsed = {"id_number": "", "amount": "", "category": "", "username": ""}

    try:
        if len(lines) > 0 and lines[0].startswith("/ID"):
            parsed["id_number"] = lines[0].replace("/ID", "").strip()
        if len(lines) > 1:
            parsed["amount"] = lines[1]
        if len(lines) > 2:
            parsed["category"] = lines[2]
        if len(lines) > 3:
            parsed["username"] = lines[-1]
    except:
        pass

    return parsed


# =====================================================
#                   CSV WRITE FUNCTION
# =====================================================
def append_row(user_id: int, row: list):
    csv_path = get_user_csv(user_id)
    with csv_lock:
        with csv_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(row)


# =====================================================
#                   COMMAND HANDLERS
# =====================================================
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    machine_status[chat_id] = True
    ensure_csv(update.effective_user.id)
    await update.message.reply_text("🟢 Machine started — ready to record messages.")


async def stop_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    machine_status[chat_id] = False
    await update.message.reply_text("🔴 Machine stopped.")


async def clear_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    clear_csv(user_id)
    await update.message.reply_text("🧹 All saved data cleared. New file created.")


async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    csv_path = get_user_csv(user_id)

    if not csv_path.exists():
        await update.message.reply_text("⚠️ You don't have any saved records yet.")
        return

    with open(csv_path, "rb") as f:
        await update.message.reply_document(document=f, filename=csv_path.name)


async def id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not machine_status.get(chat_id, False):
        return

    user_id = update.effective_user.id
    parsed = parse_message(update.message.text)

    if not parsed["id_number"]:
        return  # ignore invalid /ID

    date_str = datetime.now(timezone.utc).strftime("%m/%d/%Y")
    row = [
        date_str,
        parsed["id_number"],
        parsed["amount"],
        parsed["category"],
        parsed["username"],
    ]
    append_row(user_id, row)

    try:
        await update.message.react("❤️")
    except:
        await update.message.reply_text("Saved ❤️")


# =====================================================
#                        MAIN
# =====================================================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("stop", stop_handler))
    app.add_handler(CommandHandler("file", file_handler))
    app.add_handler(CommandHandler("clear", clear_handler))
    app.add_handler(CommandHandler("id", id_handler))

    # Handle forwarded messages (text or photo caption)
    app.add_handler(MessageHandler(filters.FORWARDED, forwarded_message_handler))

    print("Bot started ✅ Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
