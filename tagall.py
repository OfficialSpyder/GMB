# modules/tagall.py

import asyncio
from telegram import Update
from telegram.ext import ContextTypes

TAGGING_PROCESSES = {}

async def tagall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /tagall, /mentionall, and /all commands."""
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ This command can only be used in groups!")
        return

    # Admin check
    member = await chat.get_member(user.id)
    if member.status not in ["administrator", "creator"]:
        await update.message.reply_text("⚠️ <b>Admin Access Only!</b> Only admins can tag members.", parse_mode="HTML")
        return

    custom_text = " ".join(context.args) if context.args else "📢 <b>ATTENTION EVERYONE!</b>"
    if update.message.reply_to_message and not context.args:
        custom_text = update.message.reply_to_message.text or custom_text

    TAGGING_PROCESSES[chat.id] = True

    status_msg = await update.message.reply_text(
        "⚡ <b>Initiating Global Mention Protocol...</b>\n"
        "💡 <i>Send /cancel to stop tagging.</i>",
        parse_mode="HTML"
    )

    try:
        admins = await chat.get_administrators()
        tagged_text = f"{custom_text}\n\n"
        count = 0

        for admin in admins:
            if not TAGGING_PROCESSES.get(chat.id, False):
                await update.message.reply_text("🛑 <b>Tagging Process Cancelled!</b>", parse_mode="HTML")
                return

            if admin.user.is_bot:
                continue

            first_name = admin.user.first_name.replace("<", "&lt;").replace(">", "&gt;")
            tagged_text += f"▪️ <a href='tg://user?id={admin.user.id}'>{first_name}</a>\n"
            count += 1

            # Batch of 5 members to prevent rate limit
            if count % 5 == 0:
                await chat.send_message(tagged_text, parse_mode="HTML")
                tagged_text = f"{custom_text}\n\n"
                await asyncio.sleep(2)

        if count % 5 != 0:
            await chat.send_message(tagged_text, parse_mode="HTML")

        await status_msg.edit_text(f"✅ <b>Global Mention Completed!</b> Tagged <code>{count}</code> members.", parse_mode="HTML")

    except Exception as e:
        await update.message.reply_text(f"❌ Error during mention: <code>{e}</code>", parse_mode="HTML")
    finally:
        TAGGING_PROCESSES.pop(chat.id, None)


async def cancel_tagall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/cancel - Stops the active tagging process."""
    chat = update.effective_chat
    if chat.id in TAGGING_PROCESSES:
        TAGGING_PROCESSES[chat.id] = False
        await update.message.reply_text("⏳ Stopping TagAll process...", parse_mode="HTML")
    else:
        await update.message.reply_text("❓ No active tagging process running.")