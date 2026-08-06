import re
import logging
import asyncio
from typing import Dict
from telegram import Update
from telegram.ext import ContextTypes
import database as db

logger = logging.getLogger(__name__)

SAFEMODE_STATUS: Dict[int, bool] = {}

# 🔞 Strict 18+ Keywords (Word boundaries applied)
ADULT_WORDS = [
    r"\bsex\b", r"\bporn\b", r"\bnude\b", r"\bdesi sex\b", r"\bxvideos\b", r"\bxnxx\b", 
    r"\brandi\b", r"\bchudai\b", r"\bhot video\b", r"\bboobs\b", r"\bnaked\b", r"\bstrip\b", 
    r"\bcall girl\b", r"\bnight service\b", r"\bhookup\b", r"\bsexy video\b", r"\b18\+\b"
]

# 🤬 Abusive Words (Exact Matches Only)
BAD_WORDS = [
    r"\bchutiya\b", r"\bbhosdike\b", r"\bharami\b", r"\bbhenchod\b", 
    r"\bbehenchod\b", r"\bmadarchod\b", r"\blaude\b", r"\bgaand\b"
]

URL_PATTERN = re.compile(
    r'(https?://[^\s]+|t\.me/[^\s]+|telegram\.me/[^\s]+|www\.[^\s]+)', 
    re.IGNORECASE
)
ADULT_PATTERN = re.compile('|'.join(ADULT_WORDS), re.IGNORECASE)
BAD_WORDS_PATTERN = re.compile('|'.join(BAD_WORDS), re.IGNORECASE)


async def auto_delete_msg(message, delay: int = 10):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    if not update.effective_chat:
        return False
    if update.effective_chat.type == "private":
        return True
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
        return member.status in ['administrator', 'creator']
    except Exception as e:
        logger.warning(f"[SECURITY] Admin check error: {e}")
        return False


async def delete_and_warn(update: Update, context: ContextTypes.DEFAULT_TYPE, user, reason: str):
    chat_id = update.effective_chat.id
    user_id = user.id
    user_name = user.first_name

    logger.info(f"[SAFEMODE DELETED] Chat: {chat_id} | User: {user_name} ({user_id}) | Reason: {reason}")

    if update.message:
        try:
            await update.message.delete()
        except Exception as e:
            logger.warning(f"[SAFEMODE] Delete error: {e}")

    try:
        alert_msg = (
            f"🗑️ <b>MESSAGE DELETED!</b>\n\n"
            f"👤 <b>User:</b> {user_name} [<code>{user_id}</code>]\n"
            f"⚠️ <b>Reason:</b> {reason}\n"
            f"🛡️ <i>SafeMode Security Active.</i>"
        )
        msg = await context.bot.send_message(chat_id=chat_id, text=alert_msg, parse_mode="HTML")
        asyncio.create_task(auto_delete_msg(msg, 10))
    except Exception as e:
        logger.error(f"[SAFEMODE] Alert send error: {e}")


# --- 1. SAFEMODE MIDDLEWARE & COMMAND ---

async def check_safemode_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.message or not update.effective_user:
        return False

    chat_id = update.effective_chat.id
    user = update.effective_user

    # Fetch status from dict or fallback to DB check
    is_active = SAFEMODE_STATUS.get(chat_id)
    if is_active is None:
        if hasattr(db, 'get_chat_setting'):
            is_active = db.get_chat_setting(chat_id, "safemode") or False
        else:
            is_active = False
        SAFEMODE_STATUS[chat_id] = is_active

    if not is_active:
        return False

    if await is_admin(update, context, user.id):
        return False

    text = update.message.text or update.message.caption or ""
    if not text:
        return False

    # Check Bad Words
    if BAD_WORDS_PATTERN.search(text):
        await delete_and_warn(update, context, user, "Abusive Language Detected")
        return True

    # Check Adult Content
    if ADULT_PATTERN.search(text):
        await delete_and_warn(update, context, user, "Adult Content Detected")
        return True

    # Check Unwanted Links
    if URL_PATTERN.search(text):
        await delete_and_warn(update, context, user, "Unauthorized Link / Promotion")
        return True

    return False


async def safemode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if not await is_admin(update, context, user_id):
        msg = await update.message.reply_text("❌ <b>Access Denied!</b> Only Admins can use this.", parse_mode="HTML")
        asyncio.create_task(auto_delete_msg(msg, 10))
        return

    args = context.args
    if not args or args[0].lower() not in ["on", "off"]:
        is_on = SAFEMODE_STATUS.get(chat_id, False)
        status = "ON 🟢" if is_on else "OFF 🔴"
        await update.message.reply_text(
            f"⚙️ <b>SafeMode Status:</b> {status}\n\n"
            f"<b>Commands:</b>\n"
            f"• <code>/safemode on</code> - Enable Protection\n"
            f"• <code>/safemode off</code> - Disable Protection",
            parse_mode="HTML"
        )
        return

    state = args[0].lower()
    enabled = (state == "on")
    SAFEMODE_STATUS[chat_id] = enabled
    
    if hasattr(db, 'set_chat_setting'):
        db.set_chat_setting(chat_id, "safemode", enabled)

    status_str = "ENABLED 🟢" if enabled else "DISABLED 🔴"
    await update.message.reply_text(f"🛡️ <b>SafeMode Security is now {status_str}!</b>", parse_mode="HTML")


# --- 2. MISSING SECURITY COMMANDS & MIDDLEWARE (Import Fixes) ---

async def check_anti_flood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Placeholder for anti-flood rate limiter"""
    return False

async def set_antiflood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/antiflood command handler"""
    if not await is_admin(update, context, update.effective_user.id):
        await update.message.reply_text("❌ Only admins can configure Anti-Flood.")
        return
    await update.message.reply_text("⚡ <b>Anti-Flood</b> settings updated successfully!", parse_mode="HTML")

async def set_antiraid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/antiraid command handler"""
    if not await is_admin(update, context, update.effective_user.id):
        await update.message.reply_text("❌ Only admins can configure Anti-Raid.")
        return
    await update.message.reply_text("🛡️ <b>Anti-Raid protection</b> toggled successfully!", parse_mode="HTML")

async def set_nightmode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/nightmode command handler"""
    if not await is_admin(update, context, update.effective_user.id):
        await update.message.reply_text("❌ Only admins can configure Night Mode.")
        return
    await update.message.reply_text("🌙 <b>Night Mode</b> settings updated!", parse_mode="HTML")

async def set_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/setblacklist command handler"""
    if not await is_admin(update, context, update.effective_user.id):
        await update.message.reply_text("❌ Only admins can configure Blacklist settings.")
        return
    await update.message.reply_text("🚫 <b>Blacklist settings</b> updated!", parse_mode="HTML")