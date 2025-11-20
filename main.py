import csv
import secrets
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# =================== CONFIG ===================
TOKEN = "8532412255:AAErqUAlFsMansssdBxKo7jpiT42adw6J38"
# ==============================================

csv_lock = Lock()
machine_status = {}
user_files = {}  # store random filenames for each user


async def forwarded_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not machine_status.get(chat_id, False):
        return  # ignore if machine off

    user_id = update.effective_user.id
    message = update.message

    # Only process forwarded messages
    if not message.forward_origin:
        return

    text = message.text or message.caption
    if not text:
        return  # skip non-text

    parsed = parse_message(text)

    # if user just forwarded text without /ID, store first 6 lines
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    lines = lines[:6]

    date_str = datetime.now(timezone.utc).strftime("%m/%d/%Y")
    row = [date_str] + lines + [""] * (5 - len(lines))  # ensure 5 columns
    append_row(user_id, row)

    # React with ❤️ (or silently ignore errors)
    try:
        await message.react("❤️")
    except Exception:
        pass


def get_user_csv(user_id: int) -> Path:
    """Get or create a random file for this user"""
    if user_id not in user_files:
        rand_tag = secrets.token_hex(4)  # random 8-char tag
        user_files[user_id] = f"report_{user_id}_{rand_tag}.csv"
    return Path(user_files[user_id])


def ensure_csv(user_id: int):
    """Ensure file exists with headers"""
    csv_path = get_user_csv(user_id)
    if not csv_path.exists():
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "id_number", "amount", "category", "username"])


def clear_csv(user_id: int):
    """Delete or reset file"""
    csv_path = get_user_csv(user_id)
    if csv_path.exists():
        csv_path.unlink()
    ensure_csv(user_id)


# ------------------ Parse message ------------------
def parse_message(text: str):
    """Parse message like /ID 136947097 ..."""
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]

    # ✅ Keep only first 6 lines
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
            parsed["username"] = lines[-1]  # last line usually username
    except Exception:
        pass

    return parsed


# ------------------ Write to CSV ------------------
def append_row(user_id: int, row: list):
    csv_path = get_user_csv(user_id)
    with csv_lock:
        with csv_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(row)


# ------------------ Commands ------------------
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    machine_status[chat_id] = True
    ensure_csv(update.effective_user.id)
    await update.message.reply_text("🟢 Machine started — ready to record /ID messages.")


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
    print("your bot have been send file ")
    if not csv_path.exists():
        await update.message.reply_text("⚠️ You don't have any saved records yet.")
        return

    with open(csv_path, "rb") as f:
        await update.message.reply_document(document=f, filename=csv_path.name)


async def id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not machine_status.get(chat_id, False):
        return  # Ignore silently if machine off

    user_id = update.effective_user.id
    text = update.message.text
    parsed = parse_message(text)

    if not parsed["id_number"]:
        return  # invalid /ID, ignore silently

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
    except Exception:
        await update.message.reply_text("save ✅")


# ------------------ Main ------------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("stop", stop_handler))
    app.add_handler(CommandHandler("file", file_handler))
    app.add_handler(CommandHandler("clear", clear_handler))
    app.add_handler(CommandHandler("ID", id_handler))

    print("Bot started ✅ Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
