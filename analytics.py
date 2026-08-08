from telegram import Update
from telegram.ext import ContextTypes
import database as db
import html

async def track_user_xp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or update.effective_user.is_bot:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    with db.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO user_xp (chat_id, user_id, xp) VALUES (?, ?, 5)
            ON CONFLICT(chat_id, user_id) DO UPDATE SET xp = xp + 5
        ''', (chat_id, user_id))
        conn.commit()

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows top active users in the chat based on XP"""
    if not update.effective_chat or not update.message:
        return

    chat_id = update.effective_chat.id
    top_users = db.get_chat_leaderboard(chat_id, limit=5)

    if not top_users:
        await update.message.reply_text("🏆 <b>Leaderboard is empty!</b>\nStart chatting to gain XP.", parse_mode="HTML")
        return

    text = "🏆 <b>CHAT LEADERBOARD (TOP 5)</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    
    for idx, (user_id, xp) in enumerate(top_users):
        user_profile = db.get_user_profile(user_id)
        name = html.escape(user_profile.get("full_name", f"User {user_id}")) if user_profile else f"User <code>{user_id}</code>"
        medal = medals[idx] if idx < len(medals) else "🏅"
        
        text += f"{medal} <b>{name}</b> — <code>{xp} XP</code>\n"

    text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    await update.message.reply_text(text, parse_mode="HTML")