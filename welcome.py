import logging
from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db

logger = logging.getLogger(__name__)

# --- DEFAULT MESSAGES & PLACEHOLDERS ---
DEFAULT_WELCOME = (
    "👋 <b>Welcome {first_name} to {chat_title}!</b>\n\n"
    "We are glad to have you here. Make sure to follow the group rules and enjoy your time!"
)

DEFAULT_GOODBYE = (
    "👋 <b>{first_name}</b> has left <b>{chat_title}</b>. We wish them all the best!"
)

def format_message(template: str, user, chat) -> str:
    """Helper function to parse variables in welcome/goodbye text"""
    username_str = f"@{user.username}" if user.username else user.first_name
    return template.format(
        first_name=user.first_name or "User",
        last_name=user.last_name or "",
        full_name=f"{user.first_name} {user.last_name or ''}".strip(),
        username=username_str,
        user_id=user.id,
        chat_title=chat.title or "this chat"
    )

# --- 1. WELCOME EVENT HANDLER ---
async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members:
        return

    chat = update.effective_chat
    
    # Get custom welcome settings from DB (if any)
    settings = db.get_welcome_settings(chat.id) if hasattr(db, 'get_welcome_settings') else {}
    custom_text = settings.get("welcome_text") if settings else None

    for user in update.message.new_chat_members:
        if user.is_bot:
            continue
            
        welcome_msg = format_message(custom_text or DEFAULT_WELCOME, user, chat)
        
        try:
            await context.bot.send_message(
                chat_id=chat.id,
                text=welcome_msg,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"[WELCOME] Error sending welcome message: {e}")

# --- 2. GOODBYE EVENT HANDLER ---
async def goodbye_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.left_chat_member:
        return

    chat = update.effective_chat
    user = update.message.left_chat_member

    # Skip if the bot itself left
    if user.id == context.bot.id:
        return

    settings = db.get_welcome_settings(chat.id) if hasattr(db, 'get_welcome_settings') else {}
    custom_text = settings.get("goodbye_text") if settings else None

    goodbye_msg = format_message(custom_text or DEFAULT_GOODBYE, user, chat)

    try:
        await context.bot.send_message(
            chat_id=chat.id,
            text=goodbye_msg,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"[GOODBYE] Error sending goodbye message: {e}")

# --- 3. CAPTCHA CALLBACK HANDLER ---
async def handle_captcha_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Verification processed.")

# --- 4. ADMIN SETTINGS COMMANDS ---
async def set_welcome_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/setwelcome <text>"""
    chat = update.effective_chat
    user = update.effective_user

    member = await chat.get_member(user.id)
    if member.status not in ["administrator", "creator"]:
        await update.message.reply_text("❌ Only admins can change welcome messages.")
        return

    if not context.args:
        await update.message.reply_text(
            "<b>Usage:</b> /setwelcome <text>\n\n"
            "<b>Placeholders available:</b>\n"
            "• <code>{first_name}</code> - User's first name\n"
            "• <code>{username}</code> - User's username\n"
            "• <code>{chat_title}</code> - Group name",
            parse_mode="HTML"
        )
        return

    text = " ".join(context.args)
    if hasattr(db, 'update_welcome_setting'):
        db.update_welcome_setting(chat.id, "welcome_text", text)
    await update.message.reply_text("✅ Custom welcome message updated successfully!")

async def set_captcha_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/setcaptcha <off/math/button>"""
    chat = update.effective_chat
    user = update.effective_user

    member = await chat.get_member(user.id)
    if member.status not in ["administrator", "creator"]:
        await update.message.reply_text("❌ Only admins can set captcha mode.")
        return

    if not context.args:
        await update.message.reply_text("Usage: <code>/setcaptcha [off/math/button]</code>", parse_mode="HTML")
        return

    mode = context.args[0].lower()
    if hasattr(db, 'update_welcome_setting'):
        db.update_welcome_setting(chat.id, "captcha_mode", mode)
    await update.message.reply_text(f"✅ Captcha mode set to <b>{mode.upper()}</b>", parse_mode="HTML")

async def toggle_clean_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/cleanwelcome"""
    chat = update.effective_chat
    user = update.effective_user

    member = await chat.get_member(user.id)
    if member.status not in ["administrator", "creator"]:
        await update.message.reply_text("❌ Only admins can toggle clean welcome.")
        return

    settings = db.get_welcome_settings(chat.id) if hasattr(db, 'get_welcome_settings') else {}
    current = settings.get("clean_welcome", False)
    new_val = not current
    
    if hasattr(db, 'update_welcome_setting'):
        db.update_welcome_setting(chat.id, "clean_welcome", new_val)
    await update.message.reply_text(f"✅ Clean Welcome: <b>{'ON' if new_val else 'OFF'}</b>", parse_mode="HTML")

async def show_welcome_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/welcome"""
    chat = update.effective_chat
    settings = db.get_welcome_settings(chat.id) if hasattr(db, 'get_welcome_settings') else {}
    
    msg = (
        f"⚙️ <b>Welcome Settings for {chat.title}:</b>\n\n"
        f"• <b>Clean Welcome:</b> {settings.get('clean_welcome', False)}\n"
        f"• <b>Captcha Mode:</b> {settings.get('captcha_mode', 'off')}\n"
        f"• <b>Custom Message:</b> {'Yes' if settings.get('welcome_text') else 'Using Default'}"
    )
    await update.message.reply_text(msg, parse_mode="HTML")