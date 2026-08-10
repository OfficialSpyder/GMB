import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError, Forbidden, BadRequest
import config
from database import get_db

logger = logging.getLogger(__name__)

async def global_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # 1. Permission Check
    if user_id not in config.SUDO_USERS:
        await update.message.reply_text("⛔ **Access Denied:** Authorization required.")
        return

    # 2. Parse Mode & Arguments
    target_mode = "users"
    args = list(context.args)

    if args and args[0] in ["-groups", "-chats"]:
        target_mode = "groups"
        args.pop(0)
    elif args and args[0] == "-all":
        target_mode = "all"
        args.pop(0)
    elif args and args[0] == "-users":
        args.pop(0)

    broadcast_msg = update.message.reply_to_message
    text_content = " ".join(args)

    if not broadcast_msg and not text_content:
        help_text = (
            "⚠️ **Usage Guide for `/broadcast`**\n\n"
            "• `/broadcast <message>` — Send to Users\n"
            "• `/broadcast -groups <message>` — Send to Groups\n"
            "• `/broadcast -all <message>` — Send to All\n"
            "• **Or Reply** to media with `/broadcast`"
        )
        await update.message.reply_text(help_text, parse_mode="Markdown")
        return

    # 3. Fetch Targets
    target_ids = []
    with get_db() as conn:
        cursor = conn.cursor()
        
        if target_mode in ["users", "all"]:
            cursor.execute("SELECT DISTINCT user_id FROM users")
            target_ids.extend([row['user_id'] for row in cursor.fetchall()])
            
        if target_mode in ["groups", "all"]:
            cursor.execute("SELECT DISTINCT chat_id FROM group_members")
            target_ids.extend([row['chat_id'] for row in cursor.fetchall() if row['chat_id'] < 0])

    target_ids = list(set(target_ids))

    if not target_ids:
        await update.message.reply_text("⚠️ Database mein koi target records nahi mile.")
        return

    status_msg = await update.message.reply_text(
        f"📢 **Broadcast Started...**\n"
        f"🎯 **Target Mode:** `{target_mode.upper()}`\n"
        f"📊 **Total Targets:** `{len(target_ids)}`"
    )

    success = 0
    failed = 0
    blocked = 0
    cleaned = 0

    # 4. Broadcast Loop + DB Auto-Cleanup
    for target_id in target_ids:
        try:
            if broadcast_msg:
                await broadcast_msg.copy(chat_id=target_id)
            else:
                await context.bot.send_message(
                    chat_id=target_id, 
                    text=text_content, 
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )
            success += 1
            await asyncio.sleep(0.05)

        except Forbidden:
            # User ne bot block kar diya -> DB se Hatao
            blocked += 1
            cleaned += remove_dead_target(target_id)

        except BadRequest as e:
            # Chat not found / Deleted Account -> DB se Hatao
            failed += 1
            if "chat not found" in str(e).lower() or "user not found" in str(e).lower():
                cleaned += remove_dead_target(target_id)

        except TelegramError as e:
            logger.warning(f"Telegram error for {target_id}: {e}")
            failed += 1

    # 5. Summary Report
    summary = (
        f"✅ **Broadcast Finished!**\n\n"
        f"👥 **Total Target:** `{len(target_ids)}`\n"
        f"🟢 **Success (Delivered):** `{success}`\n"
        f"🚫 **Blocked:** `{blocked}`\n"
        f"❌ **Failed:** `{failed}`\n"
        f"🧹 **DB Cleaned (Removed Dead Users):** `{cleaned}`"
    )
    await status_msg.edit_text(summary, parse_mode="Markdown")


def remove_dead_target(target_id: int) -> int:
    """Helper function to remove invalid users/groups from DB."""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            if target_id > 0:
                cursor.execute("DELETE FROM users WHERE user_id = ?", (target_id,))
            else:
                cursor.execute("DELETE FROM group_members WHERE chat_id = ?", (target_id,))
            return cursor.rowcount
    except Exception as e:
        logger.error(f"Error cleaning dead ID {target_id}: {e}")
        return 0
