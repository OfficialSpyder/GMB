import re
from telegram import Update
from telegram.ext import ContextTypes
import database as db

URL_REGEX = re.compile(r'(https?://[^\s]+)|(t\.me/[^\s]+)|(telegram\.me/[^\s]+)', re.IGNORECASE)

# Valid lockable types
VALID_LOCKS = ["stickers", "media", "forward", "links"]

async def is_user_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.effective_chat or not update.effective_user:
        return False
    if update.effective_chat.type == "private":
        return True
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
        return member.status in ["administrator", "creator"]
    except Exception:
        return False

# --- 1. LOCK COMMAND ---
async def lock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/lock <type> - Lock specific media/content types"""
    chat = update.effective_chat
    user = update.effective_user

    if not await is_user_admin(update, context):
        await update.message.reply_text("❌ Only admins can change lock settings.")
        return

    if not context.args:
        await update.message.reply_text(
            "<b>Usage:</b> <code>/lock [type]</code>\n\n"
            "<b>Available locks:</b>\n"
            "• <code>stickers</code> - Block stickers & GIFs\n"
            "• <code>media</code> - Block photos, videos, audio & docs\n"
            "• <code>forward</code> - Block forwarded messages\n"
            "• <code>links</code> - Block web links & telegram URLs",
            parse_mode="HTML"
        )
        return

    lock_type = context.args[0].lower()
    if lock_type not in VALID_LOCKS:
        await update.message.reply_text(f"❌ Invalid lock type. Choose from: <code>{', '.join(VALID_LOCKS)}</code>", parse_mode="HTML")
        return

    # Update lock state in DB
    if hasattr(db, 'set_chat_lock'):
        db.set_chat_lock(chat.id, lock_type, True)
    elif hasattr(db, 'update_chat_locks'):
        db.update_chat_locks(chat.id, lock_type, True)

    await update.message.reply_text(f"🔒 <b>{lock_type.capitalize()}</b> have been <b>LOCKED</b> for non-admin members.", parse_mode="HTML")

# --- 2. UNLOCK COMMAND ---
async def unlock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/unlock <type> - Unlock specific content types"""
    chat = update.effective_chat

    if not await is_user_admin(update, context):
        await update.message.reply_text("❌ Only admins can change lock settings.")
        return

    if not context.args:
        await update.message.reply_text("<b>Usage:</b> <code>/unlock [type]</code>", parse_mode="HTML")
        return

    lock_type = context.args[0].lower()
    if lock_type not in VALID_LOCKS:
        await update.message.reply_text(f"❌ Invalid lock type. Choose from: <code>{', '.join(VALID_LOCKS)}</code>", parse_mode="HTML")
        return

    # Update lock state in DB
    if hasattr(db, 'set_chat_lock'):
        db.set_chat_lock(chat.id, lock_type, False)
    elif hasattr(db, 'update_chat_locks'):
        db.update_chat_locks(chat.id, lock_type, False)

    await update.message.reply_text(f"🔓 <b>{lock_type.capitalize()}</b> have been <b>UNLOCKED</b>.", parse_mode="HTML")

# --- 3. LIST LOCKS COMMAND ---
async def list_locks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/locks - View current chat lock statuses"""
    chat = update.effective_chat
    
    try:
        locks = db.get_chat_locks(chat.id) or {}
    except Exception:
        locks = {}

    msg = f"🔒 <b>Lock Status for {chat.title}:</b>\n\n"
    for lock_item in VALID_LOCKS:
        status = "Locked 🔒" if locks.get(lock_item) else "Unlocked 🔓"
        msg += f"• <b>{lock_item.capitalize()}:</b> {status}\n"

    await update.message.reply_text(msg, parse_mode="HTML")

# --- 4. MIDDLEWARE HANDLER ---
async def check_locks_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.message or not update.effective_user:
        return False

    chat_id = update.effective_chat.id

    # Admins par locks apply nahi hote
    if await is_user_admin(update, context):
        return False

    try:
        locks = db.get_chat_locks(chat_id) or {}
    except Exception:
        return False

    msg = update.message
    should_delete = False

    # 1. Check Stickers / Animations
    if locks.get("stickers") and (msg.sticker or msg.animation):
        should_delete = True

    # 2. Check Media
    elif locks.get("media") and (msg.photo or msg.video or msg.document or msg.voice or msg.audio):
        should_delete = True

    # 3. Check Forwards
    elif locks.get("forward") and (msg.forward_from or msg.forward_from_chat or msg.forward_date):
        should_delete = True

    # 4. Check Links
    elif locks.get("links"):
        text = msg.text or msg.caption or ""
        if URL_REGEX.search(text):
            should_delete = True

    if should_delete:
        try:
            await msg.delete()
            return True
        except Exception as e:
            print(f"[LOCKS] Delete Error: {e}")

    return False