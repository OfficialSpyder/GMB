import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime

DB_PATH = "spy_bot.db"

def get_db_connection():
    """Centralized database connection factory with performance PRAGMAs."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=15.0)
    conn.row_factory = sqlite3.Row
    
    # Speed, Cache & Concurrency Optimizations
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA cache_size=-64000;")  # 64MB Cache
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA foreign_keys=ON;")     # Enforce integrity
    return conn

@contextmanager
def get_db():
    """Context manager for safe, auto-committing thread-safe database operations."""
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()  # Auto-commit on normal exit
    except Exception as e:
        conn.rollback()  # Auto-rollback on error
        raise e
    finally:
        conn.close()

# ---------------------------------------------------------
# DATABASE INITIALIZATION & SCHEMA SETUP
# ---------------------------------------------------------

def init_db():
    """Initializes all required tables and indexes safely in one place."""
    with get_db() as conn:
        cursor = conn.cursor()

        # 1. Users Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT
            )
        """)

        # 2. User History Logs Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                event_type TEXT,
                details TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 3. Group Members Tracking Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS group_members (
                chat_id INTEGER,
                user_id INTEGER,
                PRIMARY KEY (chat_id, user_id)
            )
        """)

        # 4. User XP Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_xp (
                chat_id INTEGER,
                user_id INTEGER,
                xp INTEGER DEFAULT 0,
                PRIMARY KEY (chat_id, user_id)
            )
        """)

        # 5. Mod Logs Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mod_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                action_type TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 6. Custom Filters Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS custom_filters (
                chat_id INTEGER,
                trigger TEXT,
                reply_text TEXT,
                PRIMARY KEY (chat_id, trigger)
            )
        """)

        # 7. Locks Table (Unified Feature Locks)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS locks (
                chat_id INTEGER PRIMARY KEY,
                lock_stickers INTEGER DEFAULT 0,
                lock_media INTEGER DEFAULT 0,
                lock_forward INTEGER DEFAULT 0
            )
        """)

        # 8. Chat Locks Table (Categorical String Locks)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_locks (
                chat_id INTEGER,
                lock_type TEXT,
                PRIMARY KEY (chat_id, lock_type)
            )
        """)

        # 9. Notes Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                chat_id INTEGER,
                note_name TEXT,
                content TEXT,
                PRIMARY KEY (chat_id, note_name)
            )
        """)

        # 10. Group Admin Status Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS group_chats (
                chat_id INTEGER PRIMARY KEY,
                is_full_admin INTEGER DEFAULT 0
            )
        """)

        # 11. Security & Nightmode Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_security (
                chat_id INTEGER PRIMARY KEY,
                antiraid_status INTEGER DEFAULT 0,
                antiflood_limit INTEGER DEFAULT 5,
                nightmode_status INTEGER DEFAULT 0,
                nightmode_start TEXT DEFAULT '00:00',
                nightmode_end TEXT DEFAULT '06:00'
            )
        """)

        # 12. Welcome Settings Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS welcome_settings (
                chat_id INTEGER PRIMARY KEY,
                welcome_text TEXT DEFAULT 'Welcome {first_name} to {chat_name}!',
                captcha_mode TEXT DEFAULT 'off',
                clean_welcome INTEGER DEFAULT 0,
                last_welcome_id INTEGER DEFAULT 0
            )
        """)

        # 13. Blacklist Words Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS blacklist_words (
                chat_id INTEGER,
                word TEXT,
                PRIMARY KEY (chat_id, word)
            )
        """)

        # 14. Global Ban Users Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gban_users (
                user_id INTEGER PRIMARY KEY,
                user_name TEXT,
                username TEXT,
                reason TEXT,
                banned_by_id INTEGER,
                banned_by_username TEXT,
                banned_at TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 15. Ungban History Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ungban_history (
                user_id INTEGER PRIMARY KEY,
                user_name TEXT,
                username TEXT,
                unbanned_by_id INTEGER,
                unbanned_by_username TEXT,
                unbanned_at TEXT
            )
        """)

        # 16. Group Rules Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS group_rules (
                chat_id INTEGER PRIMARY KEY,
                rules_text TEXT
            )
        """)

        # 17. Pending Captchas Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_captchas (
                chat_id INTEGER,
                user_id INTEGER,
                PRIMARY KEY (chat_id, user_id)
            )
        """)

        # High Performance Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_xp ON user_xp (chat_id, xp DESC);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mod_logs ON mod_logs (chat_id, action_type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_filters ON custom_filters (chat_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_history ON user_history (user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_group_members_user ON group_members (user_id);")

# Safe Module Initialization
init_db()

# ---------------------------------------------------------
# USER & PROFILE MANAGEMENT
# ---------------------------------------------------------

def save_user_profile(user_id: int, username: str, full_name: str):
    """Save or update initial user profile."""
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
            (user_id, username, full_name)
        )

def get_user_profile(user_id: int):
    """Fetch user profile details."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username, full_name FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_user_by_username(username: str):
    """Fetch user profile and ID by username (case-insensitive)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, full_name FROM users WHERE LOWER(username) = LOWER(?)", (username,))
        row = cursor.fetchone()
        return dict(row) if row else None

def update_user_username(user_id: int, new_username: str):
    """Update tracked username."""
    with get_db() as conn:
        conn.execute("UPDATE users SET username = ? WHERE user_id = ?", (new_username, user_id))

def update_user_fullname(user_id: int, new_fullname: str):
    """Update tracked full name."""
    with get_db() as conn:
        conn.execute("UPDATE users SET full_name = ? WHERE user_id = ?", (new_fullname, user_id))

# ---------------------------------------------------------
# USER HISTORY & GROUP TRACKING
# ---------------------------------------------------------

def add_user_history(user_id: int, event_type: str, details: str):
    """Log name/username change events."""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO user_history (user_id, event_type, details) VALUES (?, ?, ?)",
            (user_id, event_type, details)
        )

def get_user_history(user_id: int, limit: int = 5):
    """Fetch recent user history records."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT event_type, details, timestamp FROM user_history WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        )
        return [dict(r) for r in cursor.fetchall()]

def track_group_member(chat_id: int, user_id: int):
    """Stores user and group relationships for tracking common groups."""
    with get_db() as conn:
        conn.execute("INSERT OR IGNORE INTO group_members (chat_id, user_id) VALUES (?, ?)", (chat_id, user_id))

def get_common_groups_count(user_id: int) -> int:
    """Safe lookup for common groups count."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT chat_id) FROM group_members WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        count = row[0] if row and row[0] else 1
        return max(count, 1)

# ---------------------------------------------------------
# XP & LEADERBOARD SYSTEM
# ---------------------------------------------------------

def add_user_xp(chat_id: int, user_id: int, amount: int = 10):
    """Increases user XP in a group chat."""
    with get_db() as conn:
        conn.execute("""
            INSERT INTO user_xp (chat_id, user_id, xp) 
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id, user_id) 
            DO UPDATE SET xp = xp + EXCLUDED.xp
        """, (chat_id, user_id, amount))

def get_chat_leaderboard(chat_id: int, limit: int = 5):
    """Fetches top users sorted by XP for a chat."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, xp FROM user_xp 
            WHERE chat_id = ? 
            ORDER BY xp DESC 
            LIMIT ?
        """, (chat_id, limit))
        return [dict(r) for r in cursor.fetchall()]

# ---------------------------------------------------------
# CUSTOM FILTERS & RULES
# ---------------------------------------------------------

def add_custom_filter(chat_id: int, trigger: str, reply_text: str):
    """Add or update a custom filter for a chat."""
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO custom_filters (chat_id, trigger, reply_text) VALUES (?, ?, ?)",
            (chat_id, trigger.lower(), reply_text)
        )

def get_filter(chat_id: int, trigger: str):
    """Get response for a specific trigger."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT reply_text FROM custom_filters WHERE chat_id = ? AND trigger = ?",
            (chat_id, trigger.lower())
        )
        row = cursor.fetchone()
        return row["reply_text"] if row else None

def remove_custom_filter(chat_id: int, trigger: str) -> bool:
    """Delete a custom filter."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM custom_filters WHERE chat_id = ? AND trigger = ?", (chat_id, trigger.lower()))
        return cursor.rowcount > 0

def get_chat_filters(chat_id: int) -> dict:
    """Returns all custom filters for a given chat."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT trigger, reply_text FROM custom_filters WHERE chat_id = ?", (chat_id,))
        return {row["trigger"]: row["reply_text"] for row in cursor.fetchall()}

def set_group_rules(chat_id: int, rules: str):
    """Set rules for a group chat."""
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO group_rules (chat_id, rules_text) VALUES (?, ?)", (chat_id, rules))

def get_group_rules(chat_id: int):
    """Fetch group rules."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT rules_text FROM group_rules WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()
        return row["rules_text"] if row else None

# ---------------------------------------------------------
# LOCKS & CHAT RESTRICTIONS
# ---------------------------------------------------------

def get_locks(chat_id: int) -> dict:
    """Fetch lock status (stickers, media, forward) for a given chat."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT lock_stickers, lock_media, lock_forward FROM locks WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()
        return dict(row) if row else {"lock_stickers": 0, "lock_media": 0, "lock_forward": 0}

def update_lock(chat_id: int, lock_type: str, status: int) -> bool:
    """Enable (1) or Disable (0) a specific lock in chat."""
    valid_locks = ["lock_stickers", "lock_media", "lock_forward"]
    if lock_type not in valid_locks:
        return False

    with get_db() as conn:
        conn.execute("INSERT OR IGNORE INTO locks (chat_id) VALUES (?)", (chat_id,))
        conn.execute(f"UPDATE locks SET {lock_type} = ? WHERE chat_id = ?", (status, chat_id))
    return True

def get_chat_locks(chat_id: int) -> dict:
    """Fetch active string-type locks for a chat as a dictionary."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT lock_type FROM chat_locks WHERE chat_id = ?", (chat_id,))
        return {row["lock_type"]: True for row in cursor.fetchall()}

def update_chat_lock(chat_id: int, lock_type: str, is_locked: bool):
    """Lock or unlock a specific feature in chat_locks table."""
    with get_db() as conn:
        if is_locked:
            conn.execute("INSERT OR IGNORE INTO chat_locks (chat_id, lock_type) VALUES (?, ?)", (chat_id, lock_type))
        else:
            conn.execute("DELETE FROM chat_locks WHERE chat_id = ? AND lock_type = ?", (chat_id, lock_type))

# ---------------------------------------------------------
# BLACKLIST MANAGEMENT
# ---------------------------------------------------------

def add_blacklist_word(chat_id: int, word: str) -> bool:
    """Adds a word to group blacklist."""
    word = word.lower().strip()
    try:
        with get_db() as conn:
            conn.execute("INSERT INTO blacklist_words (chat_id, word) VALUES (?, ?)", (chat_id, word))
            return True
    except sqlite3.IntegrityError:
        return False

def remove_blacklist_word(chat_id: int, word: str) -> bool:
    """Removes a word from group blacklist."""
    word = word.lower().strip()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM blacklist_words WHERE chat_id = ? AND word = ?", (chat_id, word))
        return cursor.rowcount > 0

def get_blacklist_words(chat_id: int) -> list:
    """Fetches all blacklisted words for a chat."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT word FROM blacklist_words WHERE chat_id = ?", (chat_id,))
        return [r["word"] for r in cursor.fetchall()]

# ---------------------------------------------------------
# SECURITY, WELCOME & CAPTCHA MANAGEMENT
# ---------------------------------------------------------

def get_security_settings(chat_id: int) -> dict:
    """Fetch security configuration for chat."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT antiraid_status, antiflood_limit, nightmode_status, nightmode_start, nightmode_end FROM chat_security WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()
        if row:
            return {
                "antiraid": row["antiraid_status"],
                "antiflood": row["antiflood_limit"],
                "nightmode": row["nightmode_status"],
                "nightmode_start": row["nightmode_start"],
                "nightmode_end": row["nightmode_end"]
            }
    return {"antiraid": 0, "antiflood": 5, "nightmode": 0, "nightmode_start": "00:00", "nightmode_end": "06:00"}

def update_security_setting(chat_id: int, column: str, value) -> bool:
    """Update specific security config."""
    valid_cols = ["antiraid_status", "antiflood_limit", "nightmode_status", "nightmode_start", "nightmode_end"]
    if column not in valid_cols:
        return False

    with get_db() as conn:
        conn.execute("INSERT OR IGNORE INTO chat_security (chat_id) VALUES (?)", (chat_id,))
        conn.execute(f"UPDATE chat_security SET {column} = ? WHERE chat_id = ?", (value, chat_id))
    return True

def get_welcome_settings(chat_id: int) -> dict:
    """Get welcome message and captcha configurations."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT welcome_text, captcha_mode, clean_welcome, last_welcome_id FROM welcome_settings WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()
        return dict(row) if row else {
            "welcome_text": "Welcome {first_name} to {chat_name}!",
            "captcha_mode": "off",
            "clean_welcome": 0,
            "last_welcome_id": 0
        }

def update_welcome_setting(chat_id: int, column: str, value) -> bool:
    """Update welcome settings."""
    valid_cols = ["welcome_text", "captcha_mode", "clean_welcome", "last_welcome_id"]
    if column not in valid_cols:
        return False

    with get_db() as conn:
        conn.execute("INSERT OR IGNORE INTO welcome_settings (chat_id) VALUES (?)", (chat_id,))
        conn.execute(f"UPDATE welcome_settings SET {column} = ? WHERE chat_id = ?", (value, chat_id))
    return True

def add_pending_captcha(chat_id: int, user_id: int):
    """Tracks users who need to solve captcha."""
    with get_db() as conn:
        conn.execute("INSERT OR IGNORE INTO pending_captchas VALUES (?, ?)", (chat_id, user_id))

def is_captcha_pending(chat_id: int, user_id: int) -> bool:
    """Checks if captcha verification is pending for a user."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM pending_captchas WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
        return bool(cursor.fetchone())

def remove_pending_captcha(chat_id: int, user_id: int):
    """Removes user from pending captchas table upon verification."""
    with get_db() as conn:
        conn.execute("DELETE FROM pending_captchas WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))

# ---------------------------------------------------------
# GBAN & UNGBAN DATABASE FUNCTIONS
# ---------------------------------------------------------

def add_gban_user(user_id: int, user_name: str, username: str, reason: str, banned_by_id: int, banned_by_username: str) -> bool:
    """Adds or updates a globally banned user in the database."""
    banned_at = datetime.now().strftime("%d-%b-%Y %I:%M %p")
    try:
        with get_db() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO gban_users (user_id, user_name, username, reason, banned_by_id, banned_by_username, banned_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, user_name, username, reason, banned_by_id, banned_by_username, banned_at))
            return True
    except Exception:
        return False

def remove_gban_user(user_id: int) -> bool:
    """Removes a user from the gban_users table."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM gban_users WHERE user_id = ?', (user_id,))
        return cursor.rowcount > 0

def add_to_ungban_history(user_id: int, user_name: str, username: str, unbanned_by_id: int, unbanned_by_username: str):
    """Saves ungban logs into the ungban_history table."""
    unbanned_at = datetime.now().strftime("%d-%b-%Y %I:%M %p")
    with get_db() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO ungban_history (user_id, user_name, username, unbanned_by_id, unbanned_by_username, unbanned_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, user_name, username, unbanned_by_id, unbanned_by_username, unbanned_at))

def is_gbanned(user_id: int):
    """Checks if a user is globally banned and returns reason, else None."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT reason FROM gban_users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        return row['reason'] if row else None

def get_all_gbanned():
    """Returns all gbanned users with all details for /gbanlist."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                user_id, 
                COALESCE(user_name, 'Unknown'), 
                COALESCE(username, '@None'), 
                COALESCE(reason, 'No reason provided'), 
                COALESCE(banned_by_username, 'Admin'), 
                COALESCE(banned_at, 'N/A') 
            FROM gban_users 
            ORDER BY user_id DESC
        ''')
        return [tuple(row) for row in cursor.fetchall()]

def get_all_ungbanned():
    """Returns all ungbanned users with details for /ungbanlist."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                user_id, 
                COALESCE(user_name, 'Unknown'), 
                COALESCE(username, '@None'), 
                COALESCE(unbanned_by_username, 'Admin'), 
                COALESCE(unbanned_at, 'N/A') 
            FROM ungban_history 
            ORDER BY user_id DESC
        ''')
        return [tuple(row) for row in cursor.fetchall()]

# ---------------------------------------------------------
# MODERATION LOGGING & BOT METRICS / STATS
# ---------------------------------------------------------

def log_mod_action(chat_id: int, action_type: str):
    """Helper to log moderation actions like BAN, MUTE, PROMOTE etc."""
    with get_db() as conn:
        conn.execute("INSERT INTO mod_logs (chat_id, action_type) VALUES (?, ?)", (chat_id, action_type.upper()))

def get_bot_global_stats() -> dict:
    """Aggregates all global metrics using high-performance queries."""
    stats = {
        "total_chats": 0, "full_admin_chats": 0, "limited_admin_chats": 0,
        "total_users": 0, "total_bans": 0, "total_unbans": 0,
        "total_mutes": 0, "promoted_count": 0, "demoted_count": 0,
        "total_notes": 0, "total_filters": 0, "locks": 0
    }

    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM users")
        stats["total_users"] = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(DISTINCT chat_id) FROM group_members")
        stats["total_chats"] = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM group_chats WHERE is_full_admin = 1")
        stats["full_admin_chats"] = cursor.fetchone()[0] or 0
        stats["limited_admin_chats"] = max(0, stats["total_chats"] - stats["full_admin_chats"])

        cursor.execute("SELECT action_type, COUNT(*) FROM mod_logs GROUP BY action_type")
        for action, count in cursor.fetchall():
            if action == "BAN": stats["total_bans"] = count
            elif action == "UNBAN": stats["total_unbans"] = count
            elif action == "MUTE": stats["total_mutes"] = count
            elif action == "PROMOTE": stats["promoted_count"] = count
            elif action == "DEMOTE": stats["demoted_count"] = count

        cursor.execute("SELECT COUNT(*) FROM notes")
        stats["total_notes"] = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM custom_filters")
        stats["total_filters"] = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM locks")
        stats["locks"] = cursor.fetchone()[0] or 0

    return stats