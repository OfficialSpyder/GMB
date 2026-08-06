import logging
import random
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ChatJoinRequestHandler,
    ContextTypes,
    filters
)
from telegram.request import HTTPXRequest

import config
import database as db

# --- 1. MODULE IMPORTS ---
from modules.admin import ban_user, unban_user, mute_user, unmute_user, kick_user, promote_user, demote_user
from modules.welcome import (
    welcome_new_member as welcome_member, 
    goodbye_member, 
    handle_captcha_callback, 
    set_welcome_text, 
    set_captcha_mode, 
    toggle_clean_welcome, 
    show_welcome_settings
)

from modules.warns import warn_user, reset_warns
from modules.spam import antispam_guard
from modules.locks import (
    lock_command, 
    unlock_command, 
    list_locks, 
    check_locks_middleware
)
from modules.filters import custom_filter_check
from modules.analytics import track_user_xp, leaderboard
from modules.reporting import report_user
from modules.broadcast import global_broadcast
from modules.approve import auto_approve_join_request
from modules.ai_brain import ai_content_filter
from modules.start import start_cmd
from modules.ping import ping_cmd
from modules.alive import alive_cmd
from modules.games import setup_games_handler
from modules.reloader import reload_module_cmd
from modules.help import help_command, help_callback_handler
from modules.notes import save_note, get_note, clear_note
from modules.pin import pin_message, unpin_message
from modules.purge import delete_message_command, purge_command, delall_command
from modules.gstat import gstat_command
from modules.stats import stats_command
from modules.userinfo import user_info_command, track_user_history
from modules.security import check_anti_flood, set_antiflood, set_antiraid, set_nightmode, set_blacklist, safemode_command, check_safemode_middleware
from modules.blacklist import add_blacklist_command, remove_blacklist_command, list_blacklist_command, check_blacklist_middleware
from modules.gban import gban_command, ungban_command, gban_list_command, ungban_list_command, gban_middleware
from modules.arena import fight_command, arena_callback_handler
from modules.tagall import tagall_command, cancel_tagall
from modules.rules_filters import (
    set_rules_command, 
    get_rules_command, 
    rules_callback_handler, 
    add_filter_command, 
    stop_filter_command, 
    list_filters_command, 
    check_custom_filters_middleware
)

from modules.economy import (
    xp_economy_middleware,
    rank_command,
    daily_command,
    bank_command,
    deposit_command,
    withdraw_command,
    pay_command,
    leaderboard_command,
    slots_command,
    coinflip_command,
    steal_command, 
    claim_crate_callback
)

# Initialize Database
db.init_db()

msg_counter = 0

# Setup Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- GLOBAL ERROR HANDLER ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Logs the error and notifies the console when a command fails."""
    logger.error("Exception while handling an update:", exc_info=context.error)

async def track_bot_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detects when the bot is demoted or removed from a group"""
    result = update.my_chat_member
    if not result:
        return

    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status

    if old_status == "administrator" and new_status in ["kicked", "left", "member"]:
        logger.info(f"[BOT STATUS] Bot was demoted/removed in chat {update.effective_chat.id} by {result.from_user.id}")

async def mystery_crate_spawner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global msg_counter
    msg_counter += 1
    
    # Spawns roughly every 45-60 messages
    if msg_counter >= random.randint(45, 60):
        msg_counter = 0
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧰 CLAIM SUPPLY DROP 🧰", callback_data="claim_crate")]
        ])
        
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=(
                    "🚨 <b>AIRDROP INCOMING!</b> 🚨\n\n"
                    "A rare <b>Mystery Supply Crate</b> just dropped in the chat!\n"
                    "First person to click the button below gets the loot!"
                ),
                parse_mode="HTML",
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"[CRATE SPAWNER] Error: {e}")

def main():
    # High-performance HTTP Request Handler
    custom_request = HTTPXRequest(
        connection_pool_size=20,  # Parallel HTTP connections allowance
        read_timeout=5.0,
        write_timeout=5.0,
        connect_timeout=5.0
    )

    app = (
        ApplicationBuilder()
        .token(config.BOT_TOKEN)
        .request(custom_request)
        .build()
    )

    # --- 1. CORE & UTILITY COMMANDS ---
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("ping", ping_cmd))
    app.add_handler(CommandHandler("alive", alive_cmd))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(help_callback_handler, pattern="^help_"))
    app.add_handler(CommandHandler("reload", reload_module_cmd))

    # --- 2. MODERATION & ADMIN COMMANDS ---
    app.add_handler(CommandHandler("ban", ban_user))
    app.add_handler(CommandHandler("unban", unban_user))
    app.add_handler(CommandHandler("mute", mute_user))
    app.add_handler(CommandHandler("unmute", unmute_user))
    app.add_handler(CommandHandler("kick", kick_user))
    app.add_handler(CommandHandler("promote", promote_user))
    app.add_handler(CommandHandler("demote", demote_user))
    app.add_handler(CommandHandler("warn", warn_user))
    app.add_handler(CommandHandler("resetwarns", reset_warns))
    
    # --- SAFEMODE COMMAND REGISTRATION ---
    app.add_handler(CommandHandler("safemode", safemode_command))

    # --- 3. MANAGEMENT & TOOLS COMMANDS ---
    app.add_handler(CommandHandler("save", save_note))
    app.add_handler(CommandHandler("get", get_note))
    app.add_handler(CommandHandler("clear", clear_note))
    app.add_handler(CommandHandler("pin", pin_message))
    app.add_handler(CommandHandler(["unpin", "unpinall"], unpin_message))
    app.add_handler(CommandHandler("del", delete_message_command))
    app.add_handler(CommandHandler("purge", purge_command))
    app.add_handler(CommandHandler(["delall", "clean"], delall_command))

    # --- 4. GAMES & WEB APP MODULE ---
    setup_games_handler(app)
    app.add_handler(CommandHandler("leaderboard", leaderboard))

    # --- 5. SYSTEM & STATS COMMANDS ---
    app.add_handler(CommandHandler("gstat", gstat_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("report", report_user))
    app.add_handler(CommandHandler("broadcast", global_broadcast))

    # --- 6. SECURITY & CHAT CONFIG COMMANDS ---
    app.add_handler(CommandHandler("antiflood", set_antiflood))
    app.add_handler(CommandHandler("antiraid", set_antiraid))
    app.add_handler(CommandHandler("nightmode", set_nightmode))
    app.add_handler(CommandHandler("lock", lock_command))
    app.add_handler(CommandHandler("unlock", unlock_command))
    app.add_handler(CommandHandler("locks", list_locks))
    app.add_handler(CommandHandler("addblacklist", add_blacklist_command))
    app.add_handler(CommandHandler("rmblacklist", remove_blacklist_command))
    app.add_handler(CommandHandler("blacklist", list_blacklist_command))

    # --- 7. GBAN COMMANDS ---
    app.add_handler(CommandHandler("gban", gban_command))
    app.add_handler(CommandHandler("ungban", ungban_command))
    app.add_handler(CommandHandler("gbanlist", gban_list_command))
    app.add_handler(CommandHandler("ungbanlist", ungban_list_command))
    app.add_handler(CommandHandler(["id", "info"], user_info_command))

    # --- 8. WELCOME, RULES & FILTERS ---
    app.add_handler(CommandHandler("setwelcome", set_welcome_text))
    app.add_handler(CommandHandler("welcome", show_welcome_settings))
    app.add_handler(CommandHandler("setcaptcha", set_captcha_mode))
    app.add_handler(CommandHandler("cleanwelcome", toggle_clean_welcome))
    app.add_handler(CommandHandler("setrules", set_rules_command))
    app.add_handler(CommandHandler("rules", get_rules_command))
    app.add_handler(CommandHandler("filter", add_filter_command))
    app.add_handler(CommandHandler("stop", stop_filter_command))
    app.add_handler(CommandHandler("filters", list_filters_command))
    
    # Register Economy Commands
    app.add_handler(CommandHandler(["rank", "profile"], rank_command))
    app.add_handler(CommandHandler("daily", daily_command))
    app.add_handler(CommandHandler("bank", bank_command))
    app.add_handler(CommandHandler("deposit", deposit_command))
    app.add_handler(CommandHandler("withdraw", withdraw_command))
    app.add_handler(CommandHandler("pay", pay_command))
    app.add_handler(CommandHandler(["top", "leaderboard"], leaderboard_command))
    app.add_handler(CommandHandler("slots", slots_command))
    app.add_handler(CommandHandler("coinflip", coinflip_command))
    app.add_handler(CommandHandler(["steal", "rob"], steal_command))
    app.add_handler(CommandHandler(["fight", "duel", "battle"], fight_command))
    app.add_handler(CommandHandler(["tagall", "all", "mentionall"], tagall_command))
    app.add_handler(CommandHandler(["cancel", "stopall"], cancel_tagall))

    # --- 9. SYSTEM LISTENERS & EVENT HANDLERS ---
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_member))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, goodbye_member))
    app.add_handler(ChatJoinRequestHandler(auto_approve_join_request))
    app.add_handler(CallbackQueryHandler(handle_captcha_callback, pattern="^verify_"))
    app.add_handler(CallbackQueryHandler(rules_callback_handler, pattern="^get_rules$"))
    app.add_handler(CallbackQueryHandler(claim_crate_callback, pattern="^claim_crate$"))
    app.add_handler(CallbackQueryHandler(arena_callback_handler, pattern="^arena_"))

    # --- 10. BACKGROUND PIPELINE (Ordered Middleware) ---
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, gban_middleware), group=-3)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, check_locks_middleware), group=-2)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, track_user_history), group=-1)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, check_anti_flood), group=-1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_blacklist_middleware), group=-1)
    
    # SafeMode Middleware (Group 0)
    app.add_handler(MessageHandler((filters.TEXT | filters.CAPTION) & ~filters.COMMAND, check_safemode_middleware), group=0)
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_custom_filters_middleware), group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, antispam_guard), group=2)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_content_filter), group=3)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, custom_filter_check), group=4)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, track_user_xp), group=5)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, xp_economy_middleware), group=5)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mystery_crate_spawner), group=6)

    # Register Error Handler
    app.add_error_handler(error_handler)

    print("🕵️‍♂️ SPY Complete Modular System Live & Operational!")
    app.run_polling()

if __name__ == "__main__":
    main()