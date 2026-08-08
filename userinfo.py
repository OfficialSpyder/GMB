import html
import sqlite3
import logging
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
import database as db

logger = logging.getLogger(__name__)

# --- Helper: Sync DB Tracking function for Background Execution ---
def _sync_track_user_history(chat_id: int, chat_type: str, user_id: int, current_username: str, current_full_name: str):
    try:
        if chat_type in ["group", "supergroup"]:
            if hasattr(db, 'track_group_member'):
                db.track_group_member(chat_id, user_id)

        user_data = db.get_user_profile(user_id) if hasattr(db, 'get_user_profile') else None

        if not user_data:
            if hasattr(db, 'save_user_profile'):
                db.save_user_profile(user_id, current_username, current_full_name)
            if hasattr(db, 'add_user_history'):
                db.add_user_history(user_id, "FIRST_SEEN", f"Name: {current_full_name} | @{current_username}")
        else:
            old_username = user_data.get("username", "") if isinstance(user_data, dict) else ""
            old_full_name = user_data.get("full_name", "") if isinstance(user_data, dict) else ""

            if old_username != current_username:
                if hasattr(db, 'add_user_history'):
                    db.add_user_history(user_id, "USERNAME_CHANGE", f"Old: @{old_username} ➔ New: @{current_username}")
                if hasattr(db, 'update_user_username'):
                    db.update_user_username(user_id, current_username)

            if old_full_name != current_full_name:
                if hasattr(db, 'add_user_history'):
                    db.add_user_history(user_id, "NAME_CHANGE", f"Old: {old_full_name} ➔ New: {current_full_name}")
                if hasattr(db, 'update_user_fullname'):
                    db.update_user_fullname(user_id, current_full_name)
    except Exception as e:
        logger.error(f"[USERINFO] History Tracking Error: {e}")

# --- 1. TRACK USER HISTORY MIDDLEWARE ---
async def track_user_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Har incoming message par user info & group presence track karta hai (Non-blocking)"""
    if not update.effective_user or update.effective_user.is_bot:
        return

    user = update.effective_user
    chat = update.effective_chat

    chat_id = chat.id if chat else 0
    chat_type = chat.type if chat else "private"
    user_id = user.id
    current_username = user.username or ""
    current_first_name = user.first_name or ""
    current_last_name = user.last_name or ""
    current_full_name = f"{current_first_name} {current_last_name}".strip()

    # Threadpool Execution to keep asyncio Event Loop fast
    asyncio.create_task(
        asyncio.to_thread(_sync_track_user_history, chat_id, chat_type, user_id, current_username, current_full_name)
    )

# --- 2. USER INFO COMMAND ---
async def user_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /id or /info"""
    if not update.message:
        return

    target_user = None
    target_user_id = None
    chat_id = update.effective_chat.id
    chat_title = html.escape(update.effective_chat.title or "Private Chat")

    # 1. Reply to Message Check
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        target_user_id = target_user.id

    # 2. Tagged / Mentioned Check (/id @username ya /id 12345678)
    elif context.args:
        arg = context.args[0].strip()
        
        if arg.startswith("@"):
            clean_username = arg.replace("@", "")
            user_data = db.get_user_by_username(clean_username) if hasattr(db, 'get_user_by_username') else None
            if user_data:
                target_user_id = user_data.get("user_id") if isinstance(user_data, dict) else user_data[0]
            else:
                await update.message.reply_text(f"❌ User <code>@{html.escape(clean_username)}</code> database me nahi mila!", parse_mode="HTML")
                return
        elif arg.isdigit():
            target_user_id = int(arg)
            try:
                target_user = await context.bot.get_chat(target_user_id)
            except Exception:
                pass

    # 3. Default: Sender ki apni ID
    if not target_user and not target_user_id:
        target_user = update.effective_user
        target_user_id = target_user.id

    # Details Fetching & Escaping
    if target_user:
        user_id = target_user.id
        raw_username = target_user.username or "None"
        raw_full_name = f"{target_user.first_name or ''} {target_user.last_name or ''}".strip()
    else:
        user_db_profile = db.get_user_profile(target_user_id) if hasattr(db, 'get_user_profile') else None
        user_id = target_user_id
        if user_db_profile and isinstance(user_db_profile, dict):
            raw_username = user_db_profile.get('username') or "None"
            raw_full_name = user_db_profile.get("full_name", "Unknown User")
        else:
            raw_username = "None"
            raw_full_name = "Unknown User"

    safe_username = f"@{html.escape(raw_username)}" if raw_username != "None" else "None"
    safe_full_name = html.escape(raw_full_name)

    # Profile link logic
    if raw_username != "None":
        user_link = f"https://t.me/{raw_username}"
    else:
        user_link = f"tg://user?id={user_id}"

    # Common Groups & History fetch
    common_groups_count = db.get_common_groups_count(user_id) if hasattr(db, 'get_common_groups_count') else 0
    history_records = db.get_user_history(user_id) if hasattr(db, 'get_user_history') else []

    if history_records:
        history_text = ""
        for record in history_records[:5]:
            if isinstance(record, dict):
                time_str = html.escape(str(record.get("timestamp", "N/A")))
                event_type = html.escape(str(record.get("event_type", "UPDATE")))
                details = html.escape(str(record.get("details", "")))
            else:
                time_str, event_type, details = "N/A", "LOG", str(record)
            history_text += f"• <code>{time_str}</code> | <b>{event_type}</b>\n  └ {details}\n"
    else:
        history_text = "• No past changes recorded yet.\n"

    # HTML Formatted Message Output
    info_message = (
        "👤 <b>USER & CHAT INFORMATION</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 <b>Target User ID:</b> <code>{user_id}</code>\n"
        f"💬 <b>Current Chat ID:</b> <code>{chat_id}</code> ({chat_title})\n"
        f"🏷️ <b>Username:</b> {safe_username}\n"
        f"👤 <b>User Name:</b> <code>{safe_full_name}</code>\n"
        f"🔗 <b>Profile Link:</b> <a href=\"{user_link}\">{safe_full_name}</a>\n"
        f"👥 <b>Common Groups:</b> <code>{common_groups_count}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📜 <b>USER HISTORY LOGS</b>\n"
        f"{history_text}"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    await update.message.reply_text(
        info_message, 
        parse_mode="HTML", 
        disable_web_page_preview=True
    )

# --- 3. DATABASE INITIALIZATION SAFETY ---
def init_user_history_db():
    try:
        conn = sqlite3.connect("MASTER_bot.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS custom_filters (
                chat_id INTEGER,
                trigger TEXT,
                response TEXT,
                PRIMARY KEY (chat_id, trigger)
            )
        """)

        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"[USERINFO DB INIT ERROR]: {e}")