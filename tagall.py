import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes
import database as db

logger = logging.getLogger(__name__)

# Active tagging sessions dictionary {chat_id: True/False}
TAGALL_SESSIONS = {}

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.effective_chat or not update.effective_user:
        return False
    if update.effective_chat.type == "private":
        return True
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
        return member.status in ["administrator", "creator"]
    except Exception:
        return False

# --- 1. TAGALL COMMAND ---
async def tagall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/tagall [custom message] - Mention ALL stored members (Active + Inactive)"""
    chat = update.effective_chat
    user = update.effective_user

    if not await is_admin(update, context):
        await update.message.reply_text("❌ <b>Only Admins can use /tagall!</b>", parse_mode="HTML")
        return

    if chat.id in TAGALL_SESSIONS and TAGALL_SESSIONS[chat.id]:
        await update.message.reply_text("⚠️ <b>A tagging process is already running!</b> Use /cancel to stop it.", parse_mode="HTML")
        return

    # Extract custom reason/text if provided
    custom_text = " ".join(context.args) if context.args else "Attention Everyone! 📢"
    
    # Fetch ALL stored members from Database for this chat (Active + Silent + Inactive)
    members_list = []
    if hasattr(db, 'get_all_chat_members'):
        members_list = db.get_all_chat_members(chat.id)
    elif hasattr(db, 'get_chat_users'):
        members_list = db.get_chat_users(chat.id)

    if not members_list:
        await update.message.reply_text(
            "⚠️ <b>No member database found for this chat yet!</b>\n\n"
            "<i>Note: As users interact or join, they get stored in DB. Currently tagall operates on all stored users.</i>", 
            parse_mode="HTML"
        )
        return

    # Start Tagging Session
    TAGALL_SESSIONS[chat.id] = True
    await update.message.reply_text(
        f"📢 <b>Starting TagAll for {len(members_list)} members...</b>\n"
        f"💬 <b>Reason:</b> {custom_text}\n\n"
        f"<i>Use /cancel or /stopall to abort.</i>", 
        parse_mode="HTML"
    )

    # Chunk into batches of 5 users per message (Telegram Limit Safe)
    batch_size = 5
    for i in range(0, len(members_list), batch_size):
        # Check if process was cancelled
        if not TAGALL_SESSIONS.get(chat.id, False):
            await update.message.reply_text("🛑 <b>TagAll process stopped!</b>", parse_mode="HTML")
            return

        batch = members_list[i:i + batch_size]
        mentions = []

        for member in batch:
            # Handle dictionary or tuple format from DB
            user_id = member.get("user_id") if isinstance(member, dict) else member[0] if isinstance(member, (tuple, list)) else member
            first_name = member.get("first_name", "User") if isinstance(member, dict) else "User"

            mentions.append(f'<a href="tg://user?id={user_id}">{first_name}</a>')

        tag_text = f"📢 <b>{custom_text}</b>\n\n" + " ".join(mentions)

        try:
            await context.bot.send_message(
                chat_id=chat.id,
                text=tag_text,
                parse_mode="HTML"
            )
            # Sleep 2 seconds between batches to avoid Telegram Rate Limit / Spam Ban
            await asyncio.sleep(2.0)
        except Exception as e:
            logger.error(f"[TAGALL] Error while tagging: {e}")
            await asyncio.sleep(3.0)

    # Clean session
    TAGALL_SESSIONS[chat.id] = False
    await update.message.reply_text("✅ <b>TagAll completed successfully for all members!</b>", parse_mode="HTML")

# --- 2. CANCEL / STOP COMMAND ---
async def cancel_tagall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/cancel or /stopall - Stops the current tagall process"""
    chat = update.effective_chat

    if not await is_admin(update, context):
        await update.message.reply_text("❌ Only admins can stop tagging.", parse_mode="HTML")
        return

    if chat.id in TAGALL_SESSIONS and TAGALL_SESSIONS[chat.id]:
        TAGALL_SESSIONS[chat.id] = False
        await update.message.reply_text("🛑 <b>Stopping TagAll process...</b>", parse_mode="HTML")
    else:
        await update.message.reply_text("ℹ️ No active TagAll process running in this chat.", parse_mode="HTML")
