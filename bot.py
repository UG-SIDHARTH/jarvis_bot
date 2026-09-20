# ===== COMBINED TELEGRAM + DISCORD BOT =====
# Run this on your own computer - YOU control everything

import asyncio
import threading
import time
import os
import base64
import sqlite3
import random
import re
import datetime
import secrets
from typing import Optional, Union, List, Dict, Any, Tuple, Set
from aiohttp import web
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ===== TELEGRAM SETUP =====
try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    import telegram.error
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("⚠️  Telegram library not installed. Run: pip install python-telegram-bot")

# ===== DISCORD SETUP =====
try:
    import discord
    from discord.ext import commands, tasks
    from discord import app_commands
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    print("⚠️  Discord library not installed. Run: pip install discord.py")

# ===== AI (GEMINI) SETUP =====
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# ===== CONFIGURATION =====
# Read tokens strictly from environment variables (.env file)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_PRIVILEGED_INTENTS = os.getenv("DISCORD_PRIVILEGED_INTENTS", "true").lower() in ("true", "1", "yes")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
AI_MODEL = os.getenv("AI_MODEL", "gemini-2.5-flash")

# Web Claim Link Server Configuration
CLAIM_SERVER_HOST = os.getenv("CLAIM_SERVER_HOST", "0.0.0.0")
CLAIM_SERVER_PORT = int(os.getenv("CLAIM_SERVER_PORT", "8080"))
CLAIM_SERVER_BASE_URL = os.getenv("CLAIM_SERVER_BASE_URL", f"http://localhost:{CLAIM_SERVER_PORT}").rstrip("/")

# ===== CONVERSATION MEMORY =====
conversation_sessions: Dict[str, List[Dict[str, Any]]] = {}

def get_session_history(session_id: str) -> List[Dict[str, Any]]:
    return conversation_sessions.get(session_id, [])

def add_to_session_history(session_id: str, role: str, text: str):
    if session_id not in conversation_sessions:
        conversation_sessions[session_id] = []
    conversation_sessions[session_id].append({"role": role, "text": text})
    if len(conversation_sessions[session_id]) > 10:
        conversation_sessions[session_id] = conversation_sessions[session_id][-10:]

def clear_session_history(session_id: str):
    if session_id in conversation_sessions:
        conversation_sessions[session_id] = []

# ===== LEVELING & XP DATABASE =====
LEVELS_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "levels.db")

def init_leveling_db():
    """Initialize SQLite database for server leveling and XP tracking."""
    try:
        with sqlite3.connect(LEVELS_DB_PATH) as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS user_levels (
                guild_id INTEGER,
                user_id INTEGER,
                text_xp INTEGER DEFAULT 0,
                voice_xp INTEGER DEFAULT 0,
                text_level INTEGER DEFAULT 0,
                voice_level INTEGER DEFAULT 0,
                last_text_xp_time REAL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            );
            """)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                moderator_id INTEGER,
                reason TEXT,
                timestamp REAL
            );
            """)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS server_badwords (
                guild_id INTEGER,
                word TEXT,
                PRIMARY KEY (guild_id, word)
            );
            """)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS temp_bans (
                guild_id INTEGER,
                user_id INTEGER,
                unban_timestamp REAL,
                reason TEXT,
                PRIMARY KEY (guild_id, user_id)
            );
            """)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS role_claim_links (
                token TEXT PRIMARY KEY,
                guild_id INTEGER,
                role_id INTEGER,
                target_user_id INTEGER,
                max_uses INTEGER DEFAULT 1,
                uses_count INTEGER DEFAULT 0,
                created_by INTEGER,
                expires_at REAL,
                created_at REAL
            );
            """)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS invite_roles (
                invite_code TEXT PRIMARY KEY,
                guild_id INTEGER,
                role_id INTEGER,
                created_by INTEGER,
                created_at REAL
            );
            """)
            conn.commit()
    except Exception as e:
        print(f"⚠️ Failed to initialize leveling & moderation DB: {e}")

def create_role_claim_link(
    guild_id: int,
    role_id: int,
    created_by: int,
    target_user_id: Optional[int] = None,
    max_uses: int = 1,
    expires_hours: Optional[float] = 24.0
) -> str:
    """Generate a unique secure token and store claim link in SQLite."""
    token = secrets.token_urlsafe(16)
    expires_at = time.time() + (expires_hours * 3600) if expires_hours else None
    try:
        with sqlite3.connect(LEVELS_DB_PATH) as conn:
            conn.execute(
                "INSERT INTO role_claim_links (token, guild_id, role_id, target_user_id, max_uses, uses_count, created_by, expires_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)",
                (token, guild_id, role_id, target_user_id, max_uses, created_by, expires_at, time.time())
            )
            conn.commit()
        return token
    except Exception as e:
        print(f"⚠️ Error creating role claim link: {e}")
        return ""

def get_role_claim_link(token: str) -> Optional[Dict[str, Any]]:
    """Retrieve role claim link details by token."""
    try:
        with sqlite3.connect(LEVELS_DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT token, guild_id, role_id, target_user_id, max_uses, uses_count, created_by, expires_at, created_at "
                "FROM role_claim_links WHERE token = ?",
                (token,)
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "token": row[0],
                "guild_id": row[1],
                "role_id": row[2],
                "target_user_id": row[3],
                "max_uses": row[4],
                "uses_count": row[5],
                "created_by": row[6],
                "expires_at": row[7],
                "created_at": row[8]
            }
    except Exception as e:
        print(f"⚠️ Error fetching role claim link: {e}")
        return None

def increment_claim_link_uses(token: str):
    """Increment the uses count of a claim link."""
    try:
        with sqlite3.connect(LEVELS_DB_PATH) as conn:
            conn.execute("UPDATE role_claim_links SET uses_count = uses_count + 1 WHERE token = ?", (token,))
            conn.commit()
    except Exception as e:
        print(f"⚠️ Error incrementing claim link uses: {e}")

def add_invite_role(invite_code: str, guild_id: int, role_id: int, created_by: int) -> bool:
    """Associate a Discord invite link with a role."""
    try:
        with sqlite3.connect(LEVELS_DB_PATH) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO invite_roles (invite_code, guild_id, role_id, created_by, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (invite_code, guild_id, role_id, created_by, time.time())
            )
            conn.commit()
        return True
    except Exception as e:
        print(f"⚠️ Error adding invite role: {e}")
        return False

def get_invite_role(guild_id: int, invite_code: str) -> Optional[int]:
    """Retrieve the role ID associated with an invite code."""
    try:
        with sqlite3.connect(LEVELS_DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT role_id FROM invite_roles WHERE guild_id = ? AND invite_code = ?",
                (guild_id, invite_code)
            )
            row = cur.fetchone()
            return row[0] if row else None
    except Exception as e:
        print(f"⚠️ Error fetching invite role: {e}")
        return None

def render_claim_html(title: str, message: str, is_error: bool = False, retry_token: Optional[str] = None) -> str:
    status_icon = "❌" if is_error else "🎉"
    accent_color = "#ef4444" if is_error else "#10b981"
    retry_html = f'<br><a href="/claim?token={retry_token}" style="display:inline-block;margin-top:16px;background:#3b82f6;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:600;">Try Again</a>' if retry_token else ''
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} — J.A.R.V.I.S.</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        body {{
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #f8fafc;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .card {{
            background: rgba(30, 41, 59, 0.7);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 40px;
            max-width: 480px;
            width: 100%;
            text-align: center;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
        }}
        .icon {{ font-size: 54px; margin-bottom: 20px; }}
        h1 {{ font-size: 24px; font-weight: 700; margin-bottom: 12px; color: {accent_color}; }}
        p {{ color: #cbd5e1; font-size: 16px; line-height: 1.6; margin-bottom: 20px; }}
        .footer {{ margin-top: 24px; font-size: 12px; color: #64748b; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">{status_icon}</div>
        <h1>{title}</h1>
        <p>{message}</p>
        {retry_html}
        <div class="footer">J.A.R.V.I.S. Protocol • Role Claim System</div>
    </div>
</body>
</html>"""

def render_claim_form_html(guild_name: str, role_name: str, token: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Claim {role_name} — {guild_name}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        body {{
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #f8fafc;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .card {{
            background: rgba(30, 41, 59, 0.7);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 40px;
            max-width: 480px;
            width: 100%;
            text-align: center;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
        }}
        .icon {{ font-size: 48px; margin-bottom: 16px; }}
        h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 8px; color: #f8fafc; }}
        .badge {{
            display: inline-block;
            background: rgba(59, 130, 246, 0.2);
            color: #60a5fa;
            border: 1px solid rgba(59, 130, 246, 0.4);
            border-radius: 9999px;
            padding: 4px 14px;
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 20px;
        }}
        p {{ color: #94a3b8; font-size: 14px; line-height: 1.5; margin-bottom: 20px; }}
        input[type="text"] {{
            width: 100%;
            padding: 12px 16px;
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid #334155;
            border-radius: 8px;
            color: #ffffff;
            font-size: 15px;
            margin-bottom: 16px;
            outline: none;
        }}
        input[type="text"]:focus {{ border-color: #3b82f6; }}
        button {{
            width: 100%;
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: #ffffff;
            font-size: 16px;
            font-weight: 600;
            padding: 12px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            box-shadow: 0 4px 6px -1px rgba(16, 185, 129, 0.3);
        }}
        button:hover {{ opacity: 0.95; transform: translateY(-1px); }}
        .hint {{ font-size: 12px; color: #64748b; margin-top: 16px; text-align: left; line-height: 1.4; }}
        .footer {{ margin-top: 24px; font-size: 12px; color: #64748b; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">🔗</div>
        <h1>Claim Role in {guild_name}</h1>
        <div class="badge">@{role_name}</div>
        <p>Enter your Discord User ID or Username below to claim this role on the server.</p>
        <form method="POST" action="/claim">
            <input type="hidden" name="token" value="{token}">
            <input type="text" name="user_id" placeholder="e.g. 123456789012345678 or Username" required autofocus>
            <button type="submit">⚡ Claim Role</button>
        </form>
        <div class="hint">
            <strong>Tip:</strong> You can find your User ID in Discord by enabling Developer Mode (User Settings > Advanced > Developer Mode), then right-clicking your avatar and selecting <em>"Copy User ID"</em>.
        </div>
        <div class="footer">J.A.R.V.I.S. Protocol • Role Claim System</div>
    </div>
</body>
</html>"""

def get_user_strikes(guild_id: int, user_id: int) -> int:
    """Count total warnings/strikes for a user in a guild."""
    try:
        with sqlite3.connect(LEVELS_DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM warnings WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
            return cur.fetchone()[0]
    except Exception as e:
        print(f"⚠️ Error counting strikes: {e}")
        return 0

def clear_user_strikes(guild_id: int, user_id: int) -> int:
    """Clear all strikes/warnings for a user. Returns number of cleared strikes."""
    try:
        with sqlite3.connect(LEVELS_DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM warnings WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
            conn.commit()
            return cur.rowcount
    except Exception as e:
        print(f"⚠️ Error clearing strikes: {e}")
        return 0

def add_temp_ban(guild_id: int, user_id: int, duration_seconds: float, reason: str):
    """Record a temporary ban to be automatically unbanned after duration."""
    unban_time = time.time() + duration_seconds
    try:
        with sqlite3.connect(LEVELS_DB_PATH) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO temp_bans (guild_id, user_id, unban_timestamp, reason) VALUES (?, ?, ?, ?)",
                (guild_id, user_id, unban_time, reason)
            )
            conn.commit()
    except Exception as e:
        print(f"⚠️ Error adding temp ban: {e}")

def remove_temp_ban(guild_id: int, user_id: int):
    """Remove a user from the temp ban list."""
    try:
        with sqlite3.connect(LEVELS_DB_PATH) as conn:
            conn.execute("DELETE FROM temp_bans WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
            conn.commit()
    except Exception as e:
        print(f"⚠️ Error removing temp ban: {e}")

def get_expired_temp_bans() -> List[Tuple[int, int, str]]:
    """Fetch temp bans whose duration has passed."""
    now = time.time()
    try:
        with sqlite3.connect(LEVELS_DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("SELECT guild_id, user_id, reason FROM temp_bans WHERE unban_timestamp <= ?", (now,))
            return cur.fetchall()
    except Exception as e:
        print(f"⚠️ Error fetching expired temp bans: {e}")
        return []

def add_warning(guild_id: int, user_id: int, moderator_id: int, reason: str) -> int:
    """Record a moderation warning in SQLite. Returns new warning ID."""
    try:
        with sqlite3.connect(LEVELS_DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO warnings (guild_id, user_id, moderator_id, reason, timestamp) VALUES (?, ?, ?, ?, ?)",
                (guild_id, user_id, moderator_id, reason, time.time())
            )
            conn.commit()
            return cur.lastrowid
    except Exception as e:
        print(f"⚠️ Error recording warning: {e}")
        return -1

def get_warnings(guild_id: int, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Retrieve warnings for a user or entire guild."""
    try:
        with sqlite3.connect(LEVELS_DB_PATH) as conn:
            cur = conn.cursor()
            if user_id:
                cur.execute(
                    "SELECT id, guild_id, user_id, moderator_id, reason, timestamp FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY id DESC",
                    (guild_id, user_id)
                )
            else:
                cur.execute(
                    "SELECT id, guild_id, user_id, moderator_id, reason, timestamp FROM warnings WHERE guild_id = ? ORDER BY id DESC LIMIT 50",
                    (guild_id,)
                )
            rows = cur.fetchall()
            return [
                {
                    "id": r[0],
                    "guild_id": r[1],
                    "user_id": r[2],
                    "moderator_id": r[3],
                    "reason": r[4],
                    "timestamp": r[5]
                }
                for r in rows
            ]
    except Exception as e:
        print(f"⚠️ Error fetching warnings: {e}")
        return []

def get_xp_needed(level: int) -> int:
    """XP needed to advance from `level` to `level + 1`."""
    return 5 * (level ** 2) + 50 * level + 100

def calculate_level_from_xp(total_xp: int) -> Tuple[int, int, int]:
    """Given total XP, compute (current_level, current_level_xp, xp_needed_for_next_level)."""
    level = 0
    xp_remaining = total_xp
    while True:
        needed = get_xp_needed(level)
        if xp_remaining >= needed:
            xp_remaining -= needed
            level += 1
        else:
            return level, xp_remaining, needed

def make_progress_bar(current: int, total: int, length: int = 14) -> str:
    """Generate a clean Discord progress bar matching modern ranking bots."""
    pct = min(1.0, max(0.0, current / total)) if total > 0 else 0.0
    filled = int(round(length * pct))
    bar = "█" * filled + "░" * (length - filled)
    return f"`[{bar}]`"

def add_text_xp(guild_id: int, user_id: int) -> Tuple[bool, int]:
    """Award text XP (15-25) with a 60-second cooldown. Returns (leveled_up, new_level)."""
    now = time.time()
    try:
        with sqlite3.connect(LEVELS_DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT text_xp, text_level, last_text_xp_time FROM user_levels WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id)
            )
            row = cur.fetchone()
            if row:
                text_xp, old_lvl, last_time = row
                if now - last_time < 60.0:
                    return False, old_lvl
                earned = random.randint(15, 25)
                new_xp = text_xp + earned
                new_lvl, _, _ = calculate_level_from_xp(new_xp)
                cur.execute(
                    "UPDATE user_levels SET text_xp = ?, text_level = ?, last_text_xp_time = ? WHERE guild_id = ? AND user_id = ?",
                    (new_xp, new_lvl, now, guild_id, user_id)
                )
            else:
                earned = random.randint(15, 25)
                new_xp = earned
                new_lvl, _, _ = calculate_level_from_xp(new_xp)
                old_lvl = 0
                cur.execute(
                    "INSERT INTO user_levels (guild_id, user_id, text_xp, voice_xp, text_level, voice_level, last_text_xp_time) "
                    "VALUES (?, ?, ?, 0, ?, 0, ?)",
                    (guild_id, user_id, new_xp, new_lvl, now)
                )
            conn.commit()
            leveled_up = new_lvl > old_lvl
            return leveled_up, new_lvl
    except Exception as e:
        print(f"⚠️ Error adding text XP: {e}")
        return False, 0

def add_voice_xp(guild_id: int, user_id: int, amount: int = 10) -> Tuple[bool, int]:
    """Award voice XP for active voice minutes. Returns (leveled_up, new_level)."""
    try:
        with sqlite3.connect(LEVELS_DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT voice_xp, voice_level FROM user_levels WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id)
            )
            row = cur.fetchone()
            if row:
                voice_xp, old_lvl = row
                new_xp = voice_xp + amount
                new_lvl, _, _ = calculate_level_from_xp(new_xp)
                cur.execute(
                    "UPDATE user_levels SET voice_xp = ?, voice_level = ? WHERE guild_id = ? AND user_id = ?",
                    (new_xp, new_lvl, guild_id, user_id)
                )
            else:
                new_xp = amount
                new_lvl, _, _ = calculate_level_from_xp(new_xp)
                old_lvl = 0
                cur.execute(
                    "INSERT INTO user_levels (guild_id, user_id, text_xp, voice_xp, text_level, voice_level, last_text_xp_time) "
                    "VALUES (?, ?, 0, ?, 0, ?, 0)",
                    (guild_id, user_id, new_xp, new_lvl)
                )
            conn.commit()
            return (new_lvl > old_lvl), new_lvl
    except Exception as e:
        print(f"⚠️ Error adding voice XP: {e}")
        return False, 0

def get_user_level_stats(guild_id: int, user_id: int) -> Dict[str, Any]:
    """Fetch user's text and voice levels, progress, and guild ranks."""
    try:
        with sqlite3.connect(LEVELS_DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT text_xp, voice_xp, (text_xp + voice_xp) as total_xp FROM user_levels WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id)
            )
            row = cur.fetchone()
            if not row:
                text_xp, voice_xp, total_xp = 0, 0, 0
            else:
                text_xp, voice_xp, total_xp = row

            cur.execute(
                "SELECT COUNT(*) + 1 FROM user_levels WHERE guild_id = ? AND text_xp > ?",
                (guild_id, text_xp)
            )
            text_rank = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(*) + 1 FROM user_levels WHERE guild_id = ? AND voice_xp > ?",
                (guild_id, voice_xp)
            )
            voice_rank = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(*) + 1 FROM user_levels WHERE guild_id = ? AND (text_xp + voice_xp) > ?",
                (guild_id, total_xp)
            )
            total_rank = cur.fetchone()[0]

            t_lvl, t_curr, t_needed = calculate_level_from_xp(text_xp)
            v_lvl, v_curr, v_needed = calculate_level_from_xp(voice_xp)

            return {
                "text_xp": text_xp,
                "text_level": t_lvl,
                "text_curr": t_curr,
                "text_needed": t_needed,
                "text_rank": text_rank,
                "voice_xp": voice_xp,
                "voice_level": v_lvl,
                "voice_curr": v_curr,
                "voice_needed": v_needed,
                "voice_rank": voice_rank,
                "total_xp": total_xp,
                "total_rank": total_rank
            }
    except Exception as e:
        print(f"⚠️ Error fetching user level stats: {e}")
        return {
            "text_xp": 0, "text_level": 0, "text_curr": 0, "text_needed": 100, "text_rank": "-",
            "voice_xp": 0, "voice_level": 0, "voice_curr": 0, "voice_needed": 100, "voice_rank": "-",
            "total_xp": 0, "total_rank": "-"
        }

def get_guild_leaderboard(guild_id: int, page: int = 1, per_page: int = 10, sort_by: str = "total") -> Tuple[List[Dict[str, Any]], int, int, int]:
    """Retrieve paginated leaderboard. sort_by can be 'total', 'text', or 'voice'."""
    order_col = "total_xp"
    if sort_by.lower() == "text":
        order_col = "text_xp"
    elif sort_by.lower() == "voice":
        order_col = "voice_xp"

    try:
        with sqlite3.connect(LEVELS_DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM user_levels WHERE guild_id = ?", (guild_id,))
            total_users = cur.fetchone()[0]

            total_pages = max(1, (total_users + per_page - 1) // per_page)
            page = max(1, min(page, total_pages))
            offset = (page - 1) * per_page

            query = f"""
            SELECT user_id, text_xp, voice_xp, (text_xp + voice_xp) as total_xp
            FROM user_levels
            WHERE guild_id = ?
            ORDER BY {order_col} DESC
            LIMIT ? OFFSET ?
            """
            cur.execute(query, (guild_id, per_page, offset))
            rows = cur.fetchall()

            results = []
            for rank_idx, (uid, tx_xp, vc_xp, tot_xp) in enumerate(rows, start=offset + 1):
                if sort_by.lower() == "text":
                    lvl, _, _ = calculate_level_from_xp(tx_xp)
                    disp_xp = tx_xp
                elif sort_by.lower() == "voice":
                    lvl, _, _ = calculate_level_from_xp(vc_xp)
                    disp_xp = vc_xp
                else:
                    lvl, _, _ = calculate_level_from_xp(tot_xp)
                    disp_xp = tot_xp

                results.append({
                    "rank": rank_idx,
                    "user_id": uid,
                    "level": lvl,
                    "xp": disp_xp,
                    "text_xp": tx_xp,
                    "voice_xp": vc_xp,
                    "total_xp": tot_xp
                })

            return results, page, total_pages, total_users
    except Exception as e:
        print(f"⚠️ Error fetching guild leaderboard: {e}")
        return [], 1, 1, 0

# ===== AI RATE LIMITER =====
ai_user_cooldowns: Dict[int, List[float]] = {}

def check_ai_rate_limit(user_id: int, is_admin: bool = False, current_time: float = None) -> Tuple[bool, float]:
    """
    Rate limit AI queries for normal users.
    Returns (is_limited, seconds_to_wait).
    - Admins bypass rate limits completely.
    - Normal users: min 10s between queries, max 5 queries per 120s window.
    """
    if is_admin:
        return False, 0.0
    now = current_time or time.time()
    if user_id not in ai_user_cooldowns:
        ai_user_cooldowns[user_id] = []

    ai_user_cooldowns[user_id] = [t for t in ai_user_cooldowns[user_id] if now - t < 120.0]
    timestamps = ai_user_cooldowns[user_id]

    if timestamps and (now - timestamps[-1]) < 10.0:
        return True, round(10.0 - (now - timestamps[-1]), 1)

    if len(timestamps) >= 5:
        return True, round(120.0 - (now - timestamps[0]), 1)

    ai_user_cooldowns[user_id].append(now)
    return False, 0.0

# ===== AUTOMOD SYSTEM =====
DISCORD_INVITE_REGEX = re.compile(
    r"(?:https?://)?(?:www\.)?(?:discord\.(?:gg|io|me|li)|discord(?:app)?\.com/invite)/[a-zA-Z0-9_-]+",
    re.IGNORECASE
)

DEFAULT_BAD_WORDS = {
    "fuck", "shit", "bitch", "asshole", "bastard", "cunt", "dickhead", "slut", "whore"
}

guild_badwords_cache: Dict[int, Set[str]] = {}

def get_guild_badwords(guild_id: int) -> Set[str]:
    """Retrieve bad words for a guild (default words + custom words)."""
    if guild_id not in guild_badwords_cache:
        words = set(DEFAULT_BAD_WORDS)
        try:
            with sqlite3.connect(LEVELS_DB_PATH) as conn:
                cur = conn.cursor()
                cur.execute("SELECT word FROM server_badwords WHERE guild_id = ?", (guild_id,))
                for r in cur.fetchall():
                    words.add(r[0].lower())
        except Exception as e:
            print(f"⚠️ Error loading bad words for guild {guild_id}: {e}")
        guild_badwords_cache[guild_id] = words
    return guild_badwords_cache[guild_id]

def add_guild_badword(guild_id: int, word: str) -> bool:
    """Add a custom bad word to the guild blacklist."""
    clean_word = word.strip().lower()
    if not clean_word:
        return False
    try:
        with sqlite3.connect(LEVELS_DB_PATH) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO server_badwords (guild_id, word) VALUES (?, ?)",
                (guild_id, clean_word)
            )
            conn.commit()
        if guild_id in guild_badwords_cache:
            guild_badwords_cache[guild_id].add(clean_word)
        return True
    except Exception as e:
        print(f"⚠️ Error adding bad word: {e}")
        return False

def remove_guild_badword(guild_id: int, word: str) -> bool:
    """Remove a custom bad word from the guild blacklist."""
    clean_word = word.strip().lower()
    try:
        with sqlite3.connect(LEVELS_DB_PATH) as conn:
            conn.execute(
                "DELETE FROM server_badwords WHERE guild_id = ? AND word = ?",
                (guild_id, clean_word)
            )
            conn.commit()
        if guild_id in guild_badwords_cache and clean_word in guild_badwords_cache[guild_id]:
            guild_badwords_cache[guild_id].remove(clean_word)
        return True
    except Exception as e:
        print(f"⚠️ Error removing bad word: {e}")
        return False

# Guild automod toggle settings: guild_id -> { rule_name: bool }
automod_guild_settings: Dict[int, Dict[str, bool]] = {}
# Mod-log channels: guild_id -> channel_id
custom_modlog_channels: Dict[int, int] = {}
# Spam tracking: (guild_id, user_id) -> list of message timestamps
user_message_times: Dict[Tuple[int, int], List[float]] = {}

def get_automod_setting(guild_id: int, rule: str) -> bool:
    """Check if an AutoMod rule is enabled for a guild (defaults to True)."""
    if guild_id not in automod_guild_settings:
        return True
    return automod_guild_settings[guild_id].get(rule.lower(), True)

def set_automod_setting(guild_id: int, rule: str, enabled: bool):
    """Enable or disable an AutoMod rule for a guild."""
    if guild_id not in automod_guild_settings:
        automod_guild_settings[guild_id] = {
            "anticaps": True,
            "antiinvites": True,
            "massmentions": True,
            "antispam": True,
            "badwords": True
        }
    automod_guild_settings[guild_id][rule.lower()] = enabled

def build_automod_alert_embed(guild_name: str, reason: str) -> discord.Embed:
    """Build the exact AutoMod warning alert embed matching the screenshot."""
    embed = discord.Embed(
        title="⚠️ AutoMod Alert: Warn",
        description=f"Action taken in **{guild_name}**",
        color=discord.Color.from_rgb(237, 66, 69)  # Discord Red
    )
    embed.add_field(name="Reason", value=f"Violation: {reason}", inline=False)
    return embed

def check_automod_violation(
    guild_id: int,
    user_id: int,
    content: str,
    mention_count: int = 0,
    is_staff: bool = False,
    current_time: float = None
) -> Optional[str]:
    """
    Check if a message violates AutoMod rules.
    Returns the violation reason string (e.g., 'Anti Caps', 'Discord Invites', 'Mass Mentions', 'Anti Spam', 'Bad Words') or None.
    """
    if is_staff:
        return None

    now = current_time or time.time()

    # 1. Anti Spam check (> 4 messages in 3 seconds)
    if get_automod_setting(guild_id, "antispam"):
        key = (guild_id, user_id)
        if key not in user_message_times:
            user_message_times[key] = []
        user_message_times[key] = [t for t in user_message_times[key] if now - t < 3.0]
        user_message_times[key].append(now)
        if len(user_message_times[key]) > 4:
            return "Anti Spam"

    # 2. Discord Invites check
    if get_automod_setting(guild_id, "antiinvites"):
        if DISCORD_INVITE_REGEX.search(content):
            return "Discord Invites"

    # 3. Mass Mentions check (> 4 mentions)
    if get_automod_setting(guild_id, "massmentions"):
        if mention_count > 4:
            return "Mass Mentions"

    # 4. Anti Caps check (>= 70% uppercase if total letters >= 8)
    if get_automod_setting(guild_id, "anticaps"):
        alpha_chars = [c for c in content if c.isalpha()]
        if len(alpha_chars) >= 8:
            upper_chars = [c for c in alpha_chars if c.isupper()]
            if (len(upper_chars) / len(alpha_chars)) >= 0.70:
                return "Anti Caps"

    # 5. Bad Words / Profanity check
    if get_automod_setting(guild_id, "badwords"):
        badwords = get_guild_badwords(guild_id)
        normalized = content.lower()
        for bw in badwords:
            pattern = r"\b" + re.escape(bw) + r"\b"
            if re.search(pattern, normalized, re.IGNORECASE):
                return "Bad Words"

    return None

def get_modlog_channel(guild: discord.Guild) -> Optional[discord.TextChannel]:
    """Find or retrieve designated mod-log channel for a server."""
    if guild.id in custom_modlog_channels:
        ch = guild.get_channel(custom_modlog_channels[guild.id])
        if ch:
            return ch
    for name in ["mod-logs", "mod-log", "automod-logs", "automod-log", "audit-log", "logs"]:
        ch = discord.utils.find(lambda c: c.name.lower() == name, guild.text_channels)
        if ch:
            return ch
    return None

# ===== AI HELPER FUNCTIONS =====
JARVIS_SYSTEM_INSTRUCTION = (
    "You are J.A.R.V.I.S., a sophisticated, witty, intelligent, and impeccably polite AI assistant "
    "(inspired by Tony Stark's J.A.R.V.I.S. in Iron Man). "
    "You address the user with refined charm (occasionally using 'sir' or addressing them by name if provided). "
    "Keep responses helpful, concise, well-structured, and formatted with markdown when appropriate."
)

def split_message(text: str, max_length: int = 2000) -> List[str]:
    """Split long messages into chunks that fit within platform character limits."""
    if len(text) <= max_length:
        return [text]
    chunks = []
    lines = text.split("\n")
    current_chunk = ""
    for line in lines:
        if len(current_chunk) + len(line) + 1 > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            while len(line) > max_length:
                chunks.append(line[:max_length])
                line = line[max_length:]
            current_chunk = line + "\n"
        else:
            current_chunk += line + "\n"
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    return chunks

async def generate_ai_response(
    prompt: str,
    user_name: Optional[str] = None,
    session_id: Optional[str] = None,
    image_data: Optional[Tuple[bytes, str]] = None
) -> str:
    """Generate an AI response using Google Gemini with J.A.R.V.I.S. persona, multi-turn memory, and vision."""
    if not GEMINI_API_KEY or GEMINI_API_KEY.strip() in ("", "your_gemini_api_key_here"):
        return (
            "⚠️ **Cognitive Systems Offline**: `GEMINI_API_KEY` is not configured.\n"
            "Please set your Gemini API key in the `.env` file to enable my AI capabilities, sir.\n"
            "*(You can get a free key at https://aistudio.google.com/)*"
        )

    user_tag = f"User ({user_name}): " if user_name else ""
    full_prompt = f"{user_tag}{prompt}"

    # Build prioritized candidate model list with automatic fallbacks
    candidate_models = []
    for m in [AI_MODEL, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash-latest"]:
        if m and m not in candidate_models:
            candidate_models.append(m)

    # Retrieve multi-turn history
    history = get_session_history(session_id) if session_id else []

    last_error = None

    for model_name in candidate_models:
        clean_name = model_name.replace("models/", "").strip()

        # 1. Try official google-genai client
        if GENAI_AVAILABLE:
            try:
                client = genai.Client(api_key=GEMINI_API_KEY)
                sdk_contents = []
                for h in history:
                    sdk_contents.append(types.Content(role=h["role"], parts=[types.Part.from_text(text=h["text"])]))

                current_parts = []
                if image_data:
                    raw_bytes, mime_type = image_data
                    current_parts.append(types.Part.from_bytes(data=raw_bytes, mime_type=mime_type))
                current_parts.append(types.Part.from_text(text=full_prompt))
                sdk_contents.append(types.Content(role="user", parts=current_parts))

                response = await client.aio.models.generate_content(
                    model=clean_name,
                    contents=sdk_contents,
                    config=types.GenerateContentConfig(
                        system_instruction=JARVIS_SYSTEM_INSTRUCTION,
                        temperature=0.7,
                    )
                )
                if response.text:
                    reply = response.text.strip()
                    if session_id:
                        add_to_session_history(session_id, "user", prompt)
                        add_to_session_history(session_id, "model", reply)
                    return reply
            except Exception as e:
                err_msg = str(e)
                last_error = err_msg
                if "404" in err_msg or "not found" in err_msg.lower():
                    continue

        # 2. Try direct HTTP fallback via httpx
        try:
            import httpx
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_name}:generateContent?key={GEMINI_API_KEY}"
            http_contents = []
            for h in history:
                http_contents.append({"role": h["role"], "parts": [{"text": h["text"]}]})

            current_parts = []
            if image_data:
                raw_bytes, mime_type = image_data
                b64 = base64.b64encode(raw_bytes).decode("utf-8")
                current_parts.append({"inline_data": {"mime_type": mime_type, "data": b64}})
            current_parts.append({"text": full_prompt})
            http_contents.append({"role": "user", "parts": current_parts})

            payload = {
                "system_instruction": {"parts": [{"text": JARVIS_SYSTEM_INSTRUCTION}]},
                "contents": http_contents
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            reply = parts[0].get("text", "").strip()
                            if session_id:
                                add_to_session_history(session_id, "user", prompt)
                                add_to_session_history(session_id, "model", reply)
                            return reply
                    return "I processed your query, sir, but no response was generated."
                elif res.status_code == 404:
                    last_error = f"Model '{clean_name}' not found (404)"
                    continue
                else:
                    return f"⚠️ My cognitive subsystems encountered an error ({res.status_code}): `{res.text[:200]}`"
        except Exception as e:
            last_error = str(e)
            continue

    return (
        f"⚠️ My cognitive subsystems encountered an error: `{last_error or 'No supported model found'}`.\n"
        "Please check your `GEMINI_API_KEY` or ensure `AI_MODEL=gemini-2.5-flash` is set in `.env`."
    )

# ===== TELEGRAM BOT FUNCTIONS =====
if TELEGRAM_AVAILABLE:
    async def telegram_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🤖 Combined Bot Active!\n"
            "Telegram commands:\n"
            "/start - Show this message\n"
            "/help - Get help\n"
            "/ask <prompt> - Ask Jarvis AI anything\n"
            "/echo <text> - I'll repeat your text\n"
            "/ping - Check if I'm alive\n\n"
            "Discord commands work in your Discord server!"
        )

    async def telegram_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "📚 **Telegram Help**\n"
            "/start - Start the bot\n"
            "/help - Show this help\n"
            "/ask <prompt> - Ask Jarvis AI anything (with memory)\n"
            "/ai <prompt> - Alias for /ask\n"
            "/reset - Clear conversation memory\n"
            "/echo <text> - Echo your message\n"
            "/ping - Pong! (latency test)\n"
            "/info - Bot information\n\n"
            "💡 You can also send direct messages or photos to chat with Jarvis AI!"
        )

    async def telegram_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
        prompt = ' '.join(context.args) if context.args else ""
        if not prompt:
            await update.message.reply_text("Usage: /ask <your question or prompt>")
            return
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        user_name = update.effective_user.first_name if update.effective_user else "User"
        session_id = f"tg_{update.effective_user.id}" if update.effective_user else "tg_default"
        reply = await generate_ai_response(prompt, user_name=user_name, session_id=session_id)
        for chunk in split_message(reply, max_length=4000):
            await update.message.reply_text(chunk)

    async def telegram_direct_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Respond to private text messages in Telegram using AI with memory."""
        if not update.message or not update.message.text:
            return
        if update.effective_chat.type == "private":
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            user_name = update.effective_user.first_name if update.effective_user else "User"
            session_id = f"tg_{update.effective_user.id}" if update.effective_user else "tg_default"
            reply = await generate_ai_response(update.message.text, user_name=user_name, session_id=session_id)
            for chunk in split_message(reply, max_length=4000):
                await update.message.reply_text(chunk)

    async def telegram_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Analyze photos sent in Telegram using Gemini vision."""
        if not update.message or not update.message.photo:
            return
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        try:
            photo = update.message.photo[-1]
            photo_file = await context.bot.get_file(photo.file_id)
            photo_bytes = await photo_file.download_as_bytearray()
            caption = update.message.caption or "Please analyze this image, sir."
            user_name = update.effective_user.first_name if update.effective_user else "User"
            session_id = f"tg_{update.effective_user.id}" if update.effective_user else "tg_default"
            reply = await generate_ai_response(
                prompt=caption,
                user_name=user_name,
                session_id=session_id,
                image_data=(bytes(photo_bytes), "image/jpeg")
            )
            for chunk in split_message(reply, max_length=4000):
                await update.message.reply_text(chunk)
        except Exception as e:
            await update.message.reply_text(f"⚠️ Failed to process photo: {e}")

    async def telegram_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Reset conversation memory in Telegram."""
        user_id = update.effective_user.id if update.effective_user else "default"
        clear_session_history(f"tg_{user_id}")
        await update.message.reply_text("🧹 Memory cleared! I am ready for a fresh conversation, sir.")

    async def telegram_echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = ' '.join(context.args) if context.args else ""
        if text:
            await update.message.reply_text(f"🔊 Echo: {text}")
        else:
            await update.message.reply_text("Usage: /echo <your message>")

    async def telegram_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🏓 Pong! Bot is responsive.")

    async def telegram_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🤖 **Combined Bot Info**\n"
            "Platform: Telegram + Discord\n"
            "Status: Running ✅\n"
            "Creator: You!\n"
            "Commands: /start, /help, /echo, /ping, /info"
        )

    async def telegram_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "❓ Unknown command. Try /help for available commands.\n"
            "Note: Discord commands work in your Discord server!"
        )

    async def telegram_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors in Telegram bot and prevent infinite conflict loop."""
        error = context.error
        if isinstance(error, telegram.error.Conflict):
            print("\n" + "=" * 60)
            print("⚠️  [TELEGRAM CONFLICT DETECTED]")
            print("   Terminated by another getUpdates request.")
            print("   Make sure only ONE bot instance is running with this token!")
            print("   Check for other Docker containers (`docker ps`) or local processes.")
            print("=" * 60)
            if context.application.updater and context.application.updater.running:
                print("🛑 Stopping Telegram polling loop to prevent spamming the API...")
                await context.application.updater.stop()
        elif isinstance(error, telegram.error.NetworkError):
            print(f"⚠️ Telegram network error: {error}")
        else:
            print(f"⚠️ Telegram error: {error}")

    def run_telegram_bot():
        """Run Telegram bot in separate thread"""
        print("🤖 Starting Telegram bot...")
        try:
            application = Application.builder().token(TELEGRAM_TOKEN).build()
            
            # Add handlers
            application.add_handler(CommandHandler("start", telegram_start))
            application.add_handler(CommandHandler("help", telegram_help))
            application.add_handler(CommandHandler("echo", telegram_echo))
            application.add_handler(CommandHandler("ping", telegram_ping))
            application.add_handler(CommandHandler("info", telegram_info))
            application.add_handler(CommandHandler("ask", telegram_ask))
            application.add_handler(CommandHandler("ai", telegram_ask))
            application.add_handler(CommandHandler("reset", telegram_reset))
            application.add_handler(MessageHandler(filters.PHOTO, telegram_photo_message))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, telegram_direct_message))
            application.add_handler(MessageHandler(filters.COMMAND, telegram_unknown))
            
            # Register error handler to avoid unhandled exception spam
            application.add_error_handler(telegram_error_handler)
            
            # Run the bot (drop_pending_updates flushes queued updates from old runs)
            application.run_polling(drop_pending_updates=True, stop_signals=None)
        except Exception as e:
            print(f"❌ Telegram bot crashed: {e}")
        print("✅ Telegram bot stopped")

# ===== DISCORD BOT FUNCTIONS =====
if DISCORD_AVAILABLE:
    intents = discord.Intents.default()
    if DISCORD_PRIVILEGED_INTENTS:
        intents.message_content = True  # Required to read message content for prefix commands
        intents.members = True          # Required for role assignment and member management
    else:
        print("ℹ️  Discord privileged intents disabled (DISCORD_PRIVILEGED_INTENTS=false).")
        print("   Prefix commands (!help, !ping) in servers will require mentioning the bot.")

    bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

    # --- Interactive Self-Role UI Components ---
    class SelfRoleButton(discord.ui.Button):
        def __init__(self, role: discord.Role):
            super().__init__(label=role.name, style=discord.ButtonStyle.primary, custom_id=f"self_role_{role.id}")
            self.role_id = role.id

        async def callback(self, interaction: discord.Interaction):
            role = interaction.guild.get_role(self.role_id)
            if not role:
                await interaction.response.send_message("❌ This role no longer exists.", ephemeral=True)
                return

            if role in interaction.user.roles:
                try:
                    await interaction.user.remove_roles(role, reason="Self-assigned role toggle")
                    await interaction.response.send_message(f"➖ Removed role **{role.name}** from you.", ephemeral=True)
                except discord.Forbidden:
                    await interaction.response.send_message("⚠️ I don't have permission to remove that role. Check my role hierarchy!", ephemeral=True)
            else:
                try:
                    await interaction.user.add_roles(role, reason="Self-assigned role toggle")
                    await interaction.response.send_message(f"➕ Added role **{role.name}** to you!", ephemeral=True)
                except discord.Forbidden:
                    await interaction.response.send_message("⚠️ I don't have permission to assign that role. Check my role hierarchy!", ephemeral=True)

    class SelfRoleView(discord.ui.View):
        def __init__(self, roles):
            super().__init__(timeout=None)  # Persistent view
            for role in roles[:25]:  # Discord limit: max 25 components
                self.add_item(SelfRoleButton(role))

    class ClaimRoleButton(discord.ui.DynamicItem[discord.ui.Button], template=r'claim_role:(?P<role_id>[0-9]+):(?P<toggle>[01])'):
        """Persistent 1-click button for members to claim a role, surviving bot restarts."""
        def __init__(
            self,
            role_id: int,
            toggle: bool = False,
            label: str = "Claim Role",
            style: discord.ButtonStyle = discord.ButtonStyle.success,
            emoji: Optional[str] = "✅"
        ):
            self.role_id = role_id
            self.toggle = toggle
            super().__init__(
                discord.ui.Button(
                    label=label,
                    style=style,
                    emoji=emoji,
                    custom_id=f"claim_role:{role_id}:{1 if toggle else 0}"
                )
            )

        @classmethod
        async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str], /):
            role_id = int(match.group('role_id'))
            toggle = bool(int(match.group('toggle')))
            return cls(role_id, toggle, label=item.label or "Claim Role", style=item.style or discord.ButtonStyle.success, emoji=item.emoji)

        async def callback(self, interaction: discord.Interaction):
            if not interaction.guild:
                await interaction.response.send_message("❌ This button can only be used within a server.", ephemeral=True)
                return

            role = interaction.guild.get_role(self.role_id)
            if not role:
                await interaction.response.send_message("❌ This role no longer exists in the server.", ephemeral=True)
                return

            if role >= interaction.guild.me.top_role:
                await interaction.response.send_message(
                    "⚠️ I cannot assign this role because it is higher than or equal to my highest role in Server Settings > Roles!",
                    ephemeral=True
                )
                return

            member = interaction.user
            if not isinstance(member, discord.Member):
                member = interaction.guild.get_member(interaction.user.id)

            if not member:
                await interaction.response.send_message("❌ Could not retrieve your member profile.", ephemeral=True)
                return

            if role in member.roles:
                if self.toggle:
                    try:
                        await member.remove_roles(role, reason="Claim Role button toggle (removed)")
                        await interaction.response.send_message(
                            f"➖ Removed **{role.name}** from you, {member.mention}.",
                            ephemeral=True
                        )
                    except discord.Forbidden:
                        await interaction.response.send_message("⚠️ I don't have permission to remove this role.", ephemeral=True)
                else:
                    await interaction.response.send_message(
                        f"ℹ️ You already have the **{role.name}** role, {member.mention}!",
                        ephemeral=True
                    )
            else:
                try:
                    await member.add_roles(role, reason="Claim Role button (granted)")
                    await interaction.response.send_message(
                        f"🎉 **Success**: You have been granted the **{role.name}** role, {member.mention}!",
                        ephemeral=True
                    )
                except discord.Forbidden:
                    await interaction.response.send_message(
                        "⚠️ I don't have permission to assign this role. Please ensure my bot role is higher than this role in Server Settings > Roles.",
                        ephemeral=True
                    )

    bot.add_dynamic_items(ClaimRoleButton)

    @tasks.loop(minutes=1)
    async def voice_xp_updater():
        """Award voice XP every minute to active members in voice channels."""
        try:
            for guild in bot.guilds:
                for vc in guild.voice_channels:
                    if guild.afk_channel and vc.id == guild.afk_channel.id:
                        continue
                    for member in vc.members:
                        if member.bot or (member.voice and (member.voice.self_deaf or member.voice.deaf)):
                            continue
                        leveled_up, new_lvl = add_voice_xp(guild.id, member.id, amount=10)
                        if leveled_up:
                            ch = guild.system_channel or vc
                            try:
                                embed = discord.Embed(
                                    title="🎉 Level Up!",
                                    description=f"{member.mention} has reached **Voice Level {new_lvl}**!",
                                    color=discord.Color.brand_green()
                                )
                                if member.display_avatar:
                                    embed.set_thumbnail(url=member.display_avatar.url)
                                await ch.send(embed=embed)
                            except Exception:
                                pass
        except Exception as e:
            print(f"⚠️ Error in voice_xp_updater: {e}")

    @tasks.loop(minutes=1)
    async def temp_ban_checker():
        """Check for expired temporary bans and unban members automatically."""
        expired = get_expired_temp_bans()
        for guild_id, user_id, reason in expired:
            guild = bot.get_guild(guild_id)
            if guild:
                try:
                    user = await bot.fetch_user(user_id)
                    await guild.unban(user, reason="Temporary ban expired (AutoMod)")
                    modlog_ch = get_modlog_channel(guild)
                    if modlog_ch:
                        embed = discord.Embed(
                            title="🔓 Temp Ban Expired",
                            description=f"**{user.name}** (`{user.id}`) has been automatically unbanned.",
                            color=discord.Color.green()
                        )
                        await modlog_ch.send(embed=embed)
                except Exception as e:
                    print(f"⚠️ Failed to unban user {user_id} in guild {guild_id}: {e}")
            remove_temp_ban(guild_id, user_id)

    # --- Tracking & Web Server State ---
    guild_invites_cache: Dict[int, Dict[str, int]] = {}
    web_server_task = None

    async def handle_claim_get(request: web.Request) -> web.Response:
        token = request.query.get("token", "").strip()
        if not token:
            return web.Response(
                text=render_claim_html("❌ Missing Token", "No claim token was provided in the link.", is_error=True),
                content_type="text/html",
                status=400
            )

        link_data = get_role_claim_link(token)
        if not link_data:
            return web.Response(
                text=render_claim_html("❌ Invalid Link", "This claim link does not exist or has expired.", is_error=True),
                content_type="text/html",
                status=404
            )

        if link_data["expires_at"] and time.time() > link_data["expires_at"]:
            return web.Response(
                text=render_claim_html("⏳ Link Expired", "This claim link has expired.", is_error=True),
                content_type="text/html",
                status=410
            )

        if link_data["max_uses"] is not None and link_data["uses_count"] >= link_data["max_uses"]:
            return web.Response(
                text=render_claim_html("⚠️ Fully Claimed", "This link has already reached its maximum number of uses.", is_error=True),
                content_type="text/html",
                status=410
            )

        guild = bot.get_guild(link_data["guild_id"])
        if not guild:
            return web.Response(
                text=render_claim_html("❌ Server Not Found", "The Discord server for this link was not found.", is_error=True),
                content_type="text/html",
                status=404
            )

        role = guild.get_role(link_data["role_id"])
        if not role:
            return web.Response(
                text=render_claim_html("❌ Role Not Found", "The role for this link no longer exists.", is_error=True),
                content_type="text/html",
                status=404
            )

        # 1. If target_user_id is already specified (personalized link):
        if link_data["target_user_id"]:
            member = guild.get_member(link_data["target_user_id"])
            if not member:
                return web.Response(
                    text=render_claim_html("❌ Member Not in Server", "You must be in the server to claim this role.", is_error=True),
                    content_type="text/html",
                    status=404
                )

            if role in member.roles:
                return web.Response(
                    text=render_claim_html("ℹ️ Already Claimed", f"You already have the <strong>{role.name}</strong> role in <strong>{guild.name}</strong>!"),
                    content_type="text/html"
                )

            if role >= guild.me.top_role:
                return web.Response(
                    text=render_claim_html("⚠️ Hierarchy Error", "Bot role must be higher than the target role in Server Settings.", is_error=True),
                    content_type="text/html",
                    status=500
                )

            try:
                await member.add_roles(role, reason=f"Claimed via web link (token: {token[:8]}...)")
                increment_claim_link_uses(token)
                return web.Response(
                    text=render_claim_html(
                        "🎉 Role Claimed Successfully!",
                        f"Congratulations, <strong>{member.display_name}</strong>! You have been granted the <strong>{role.name}</strong> role in <strong>{guild.name}</strong>.<br><br>You can now return to Discord."
                    ),
                    content_type="text/html"
                )
            except Exception as e:
                return web.Response(
                    text=render_claim_html("❌ Error Assigning Role", str(e), is_error=True),
                    content_type="text/html",
                    status=500
                )

        # 2. If open link: show the claim form
        return web.Response(
            text=render_claim_form_html(guild.name, role.name, token),
            content_type="text/html"
        )

    async def handle_claim_post(request: web.Request) -> web.Response:
        data = await request.post()
        token = data.get("token", "").strip()
        user_input = data.get("user_id", "").strip()

        if not token or not user_input:
            return web.Response(
                text=render_claim_html("❌ Missing Information", "Please enter your Discord User ID or Username.", is_error=True, retry_token=token),
                content_type="text/html",
                status=400
            )

        link_data = get_role_claim_link(token)
        if not link_data or (link_data["max_uses"] and link_data["uses_count"] >= link_data["max_uses"]):
            return web.Response(
                text=render_claim_html("⚠️ Invalid Link", "This link is no longer valid or has been fully claimed.", is_error=True),
                content_type="text/html",
                status=410
            )

        if link_data["expires_at"] and time.time() > link_data["expires_at"]:
            return web.Response(
                text=render_claim_html("⏳ Link Expired", "This claim link has expired.", is_error=True),
                content_type="text/html",
                status=410
            )

        guild = bot.get_guild(link_data["guild_id"])
        role = guild.get_role(link_data["role_id"]) if guild else None
        if not guild or not role:
            return web.Response(
                text=render_claim_html("❌ Server or Role Not Found", "Could not locate the server or role.", is_error=True),
                content_type="text/html",
                status=404
            )

        # Find member by ID or username
        member = None
        if user_input.isdigit():
            member = guild.get_member(int(user_input))
        if not member:
            member = discord.utils.find(lambda m: m.name.lower() == user_input.lower() or m.display_name.lower() == user_input.lower(), guild.members)

        if not member:
            return web.Response(
                text=render_claim_html(
                    "❌ Member Not Found",
                    f"Could not find member <strong>{user_input}</strong> in <strong>{guild.name}</strong>.<br><br>Make sure you have joined the server and entered your exact Discord User ID or Username.",
                    is_error=True,
                    retry_token=token
                ),
                content_type="text/html",
                status=404
            )

        if role in member.roles:
            return web.Response(
                text=render_claim_html(
                    "ℹ️ Already Claimed",
                    f"<strong>{member.display_name}</strong> already has the <strong>{role.name}</strong> role in <strong>{guild.name}</strong>!"
                ),
                content_type="text/html"
            )

        if role >= guild.me.top_role:
            return web.Response(
                text=render_claim_html("⚠️ Hierarchy Error", "Bot role must be higher than the target role in Server Settings.", is_error=True),
                content_type="text/html",
                status=500
            )

        try:
            await member.add_roles(role, reason=f"Claimed via web link (token: {token[:8]}...)")
            increment_claim_link_uses(token)
            return web.Response(
                text=render_claim_html(
                    "🎉 Role Claimed Successfully!",
                    f"Congratulations, <strong>{member.display_name}</strong>! You have been granted the <strong>{role.name}</strong> role in <strong>{guild.name}</strong>.<br><br>You can now close this tab and return to Discord."
                ),
                content_type="text/html"
            )
        except Exception as e:
            return web.Response(
                text=render_claim_html("❌ Error Assigning Role", str(e), is_error=True),
                content_type="text/html",
                status=500
            )

    async def start_web_claim_server():
        """Start the lightweight web claim server using aiohttp."""
        try:
            app = web.Application()
            app.router.add_get('/claim', handle_claim_get)
            app.router.add_post('/claim', handle_claim_post)
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, CLAIM_SERVER_HOST, CLAIM_SERVER_PORT)
            await site.start()
            print(f"🌐 Role Claim Web Server running on {CLAIM_SERVER_BASE_URL}/claim")
        except Exception as e:
            print(f"⚠️ Could not start Role Claim Web Server on port {CLAIM_SERVER_PORT}: {e}")

    @bot.event
    async def on_ready():
        global web_server_task
        print(f'🤖 Discord bot logged in as {bot.user} (ID: {bot.user.id})')
        print('------')
        # Initialize leveling database
        init_leveling_db()

        # Start web claim server if not already running
        if web_server_task is None:
            web_server_task = bot.loop.create_task(start_web_claim_server())

        # Cache guild invites for tracked role assignment
        for g in bot.guilds:
            try:
                invites = await g.invites()
                guild_invites_cache[g.id] = {inv.code: inv.uses for inv in invites}
            except Exception:
                pass

        # Start voice XP loop if not already running
        if not voice_xp_updater.is_running():
            voice_xp_updater.start()

        # Start temporary ban checker loop if not already running
        if not temp_ban_checker.is_running():
            temp_ban_checker.start()

        # Sync slash commands with Discord
        try:
            synced = await bot.tree.sync()
            print(f"✅ Synced {len(synced)} slash command(s) with Discord!")
        except Exception as e:
            print(f"⚠️ Failed to sync slash commands: {e}")

        # Default Rich Presence: Competing in Competitive (Playing Solo)
        activity = discord.Activity(
            type=discord.ActivityType.competing,
            name="Competitive",
            state="Playing Solo"
        )
        await bot.change_presence(activity=activity)

    @bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, commands.CommandNotFound):
            await ctx.send("❓ Unknown command. Type `!help` for available commands.")
        elif isinstance(error, commands.MissingPermissions):
            missing = ", ".join(f"`{perm}`" for perm in error.missing_permissions)
            await ctx.send(f"⛔ You don't have permission to use this command! Missing: {missing}")
        elif isinstance(error, commands.BotMissingPermissions):
            missing = ", ".join(f"`{perm}`" for perm in error.missing_permissions)
            await ctx.send(f"⚠️ I don't have the required permissions to do that! Missing: {missing}")
        elif isinstance(error, commands.RoleNotFound):
            await ctx.send(f"❌ Role `{error.argument}` not found. Check the name or mention.")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send(f"❌ Member `{error.argument}` not found. Please mention them or use their ID.")
        elif isinstance(error, commands.ChannelNotFound):
            await ctx.send(f"❌ Channel `{error.argument}` not found.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"⚠️ Missing required argument: `{error.param.name}`. Check `!help` for usage.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"⚠️ Invalid argument: {str(error)}")
        else:
            await ctx.send(f"⚠️ An error occurred: {str(error)}")
            print(f"Discord error: {error}")

    async def is_admin_user(user: Union[discord.User, discord.Member], guild: Optional[discord.Guild] = None) -> bool:
        """Check if a user is a server administrator or bot owner."""
        try:
            if await bot.is_owner(user):
                return True
        except Exception:
            pass

        if guild:
            if isinstance(user, discord.Member):
                return user.guild_permissions.administrator
            m = guild.get_member(user.id)
            if m and m.guild_permissions.administrator:
                return True
            return False

        # In DMs (no guild context), allow if they are an administrator in at least one mutual guild
        for g in bot.guilds:
            m = g.get_member(user.id)
            if m and m.guild_permissions.administrator:
                return True
        return False

    @bot.event
    async def on_message(message: discord.Message):
        if message.author.bot:
            return

        # AutoMod Check for guild messages (before XP or commands)
        if message.guild:
            is_staff = False
            if isinstance(message.author, discord.Member):
                is_staff = (
                    message.author.guild_permissions.manage_messages
                    or message.author.guild_permissions.administrator
                )

            mention_count = len(message.mentions) + len(message.role_mentions)
            violation = check_automod_violation(
                guild_id=message.guild.id,
                user_id=message.author.id,
                content=message.content,
                mention_count=mention_count,
                is_staff=is_staff
            )

            if violation:
                # 1. Delete message
                try:
                    await message.delete()
                except Exception:
                    pass

                # 2. Record warning and count strikes
                warn_id = add_warning(message.guild.id, message.author.id, bot.user.id, f"AutoMod: {violation}")
                strikes = get_user_strikes(message.guild.id, message.author.id)

                # 3. Determine graduated sanction
                if strikes >= 5:
                    # Tier 3: 24-Hour Temporary Ban
                    dm_embed = discord.Embed(
                        title="⛔ AutoMod Alert: Temporary Ban",
                        description=f"Action taken in **{message.guild.name}**",
                        color=discord.Color.from_rgb(237, 66, 69)
                    )
                    dm_embed.add_field(name="Reason", value=f"Violation: {violation}", inline=False)
                    dm_embed.add_field(name="Strikes", value=f"{strikes}/5 (Limit Reached)", inline=True)
                    dm_embed.add_field(name="Duration", value="24 Hours (Temporary Ban)", inline=True)
                    dm_embed.add_field(name="Appeals", value="An administrator can cancel or reverse this ban using `/unban`.", inline=False)
                    try:
                        await message.author.send(embed=dm_embed)
                    except Exception:
                        pass

                    add_temp_ban(message.guild.id, message.author.id, 86400, f"AutoMod: {violation} (Strike {strikes}/5)")
                    try:
                        await message.guild.ban(message.author, reason=f"AutoMod: {violation} (Strike {strikes}/5 - Temp Ban)", delete_message_days=0)
                    except Exception as e:
                        print(f"⚠️ Failed to ban member: {e}")

                    modlog_ch = get_modlog_channel(message.guild)
                    if modlog_ch:
                        log_embed = discord.Embed(
                            title="⛔ AutoMod Alert: Temporary Ban",
                            description=f"**{message.author.name}** (`{message.author.id}`) was temporarily banned (24h) in {message.channel.mention}",
                            color=discord.Color.from_rgb(237, 66, 69)
                        )
                        log_embed.add_field(name="Reason", value=f"Violation: {violation}", inline=True)
                        log_embed.add_field(name="Strikes", value=f"{strikes}/5", inline=True)
                        content_preview = f"`{message.clean_content[:400]}`" if message.clean_content else "*No text*"
                        log_embed.add_field(name="Offending Content", value=content_preview, inline=False)
                        try:
                            await modlog_ch.send(embed=log_embed)
                        except Exception:
                            pass

                    try:
                        notice = await message.channel.send(
                            f"⛔ {message.author.mention} has been temporarily banned for 24 hours. (Strike {strikes}/5 • Violation: **{violation}**)"
                        )
                        await asyncio.sleep(6)
                        await notice.delete()
                    except Exception:
                        pass

                elif strikes >= 3:
                    # Tier 2: 10-Minute Timeout
                    dm_embed = discord.Embed(
                        title="⚠️ AutoMod Alert: Timeout",
                        description=f"Action taken in **{message.guild.name}**",
                        color=discord.Color.from_rgb(237, 66, 69)
                    )
                    dm_embed.add_field(name="Reason", value=f"Violation: {violation}", inline=False)
                    dm_embed.add_field(name="Strikes", value=f"{strikes}/5", inline=True)
                    dm_embed.add_field(name="Duration", value="10 Minutes (Timeout)", inline=True)
                    dm_embed.add_field(name="Note", value="An administrator can cancel this timeout using `/untimeout`.", inline=False)
                    try:
                        await message.author.send(embed=dm_embed)
                    except Exception:
                        pass

                    try:
                        await message.author.timeout(datetime.timedelta(minutes=10), reason=f"AutoMod: {violation} (Strike {strikes}/5)")
                    except Exception as e:
                        print(f"⚠️ Failed to timeout member: {e}")

                    modlog_ch = get_modlog_channel(message.guild)
                    if modlog_ch:
                        log_embed = discord.Embed(
                            title="⚠️ AutoMod Alert: Timeout",
                            description=f"Action taken on {message.author.mention} in {message.channel.mention}",
                            color=discord.Color.from_rgb(237, 66, 69)
                        )
                        log_embed.add_field(name="Reason", value=f"Violation: {violation}", inline=True)
                        log_embed.add_field(name="Strikes", value=f"{strikes}/5 (10m Timeout)", inline=True)
                        content_preview = f"`{message.clean_content[:400]}`" if message.clean_content else "*No text*"
                        log_embed.add_field(name="Offending Content", value=content_preview, inline=False)
                        try:
                            await modlog_ch.send(embed=log_embed)
                        except Exception:
                            pass

                    try:
                        notice = await message.channel.send(
                            f"⏳ {message.author.mention} has been timed out for 10 minutes. (Strike {strikes}/5 • Violation: **{violation}**)"
                        )
                        await asyncio.sleep(5)
                        await notice.delete()
                    except Exception:
                        pass

                else:
                    # Tier 1: Warning
                    alert_embed = build_automod_alert_embed(message.guild.name, f"{violation} (Strike {strikes}/5)")
                    try:
                        await message.author.send(embed=alert_embed)
                    except Exception:
                        pass

                    modlog_ch = get_modlog_channel(message.guild)
                    if modlog_ch:
                        log_embed = discord.Embed(
                            title="⚠️ AutoMod Alert: Warn",
                            description=f"Action taken on {message.author.mention} in {message.channel.mention}",
                            color=discord.Color.from_rgb(237, 66, 69)
                        )
                        log_embed.add_field(name="Reason", value=f"Violation: {violation}", inline=True)
                        log_embed.add_field(name="Strikes", value=f"{strikes}/5", inline=True)
                        content_preview = f"`{message.clean_content[:400]}`" if message.clean_content else "*No text*"
                        log_embed.add_field(name="Offending Content", value=content_preview, inline=False)
                        try:
                            await modlog_ch.send(embed=log_embed)
                        except Exception:
                            pass

                    try:
                        notice = await message.channel.send(
                            f"⚠️ {message.author.mention}, your message was removed. (Violation: **{violation}** • Strike {strikes}/5)"
                        )
                        await asyncio.sleep(5)
                        await notice.delete()
                    except Exception:
                        pass

                return  # Halt processing

        # Award Text XP (with 60s cooldown)
        if message.guild:
            leveled_up, new_lvl = add_text_xp(message.guild.id, message.author.id)
            if leveled_up:
                embed = discord.Embed(
                    title="🎉 Level Up!",
                    description=f"{message.author.mention} has reached level **{new_lvl}**!",
                    color=discord.Color.gold()
                )
                if message.author.display_avatar:
                    embed.set_thumbnail(url=message.author.display_avatar.url)
                try:
                    await message.channel.send(embed=embed)
                except Exception:
                    pass

        # 1. Discord Direct Message (DM) Auto-Chat (Admin Only)
        if message.guild is None:
            prompt = message.content.strip()
            image_data = None
            if message.attachments:
                for att in message.attachments:
                    if att.content_type and att.content_type.startswith("image/"):
                        try:
                            data = await att.read()
                            image_data = (data, att.content_type)
                            break
                        except Exception:
                            pass

            if not prompt and image_data:
                prompt = "Please analyze this image, sir."

            if prompt or image_data:
                if not await is_admin_user(message.author, None):
                    await message.channel.send("⛔ **Access Denied**: J.A.R.V.I.S. AI cognitive systems are restricted to server administrators only, sir.")
                    return

                is_limited, wait_sec = check_ai_rate_limit(message.author.id, is_admin=True)
                if is_limited:
                    await message.channel.send(f"⏳ **Rate limit reached**: Please wait **{wait_sec}s** before asking another question, sir.")
                    return

                async with message.channel.typing():
                    response = await generate_ai_response(
                        prompt=prompt,
                        user_name=message.author.display_name,
                        session_id=f"discord_dm_{message.author.id}",
                        image_data=image_data
                    )
                    chunks = split_message(response, max_length=1950)
                    for chunk in chunks:
                        await message.channel.send(chunk)
            return

        # 2. Server Mention (@Jarvis) (Admin Only)
        if bot.user and bot.user.mentioned_in(message) and not message.mention_everyone:
            prompt = message.content
            for mention in [f"<@{bot.user.id}>", f"<@!{bot.user.id}>"]:
                prompt = prompt.replace(mention, "")
            prompt = prompt.strip()

            image_data = None
            if message.attachments:
                for att in message.attachments:
                    if att.content_type and att.content_type.startswith("image/"):
                        try:
                            data = await att.read()
                            image_data = (data, att.content_type)
                            break
                        except Exception:
                            pass

            if not prompt and image_data:
                prompt = "Please analyze this image, sir."

            if prompt or image_data:
                if not await is_admin_user(message.author, message.guild):
                    await message.reply("⛔ **Access Denied**: J.A.R.V.I.S. AI cognitive systems are restricted to server administrators only, sir.", mention_author=False)
                    return

                is_limited, wait_sec = check_ai_rate_limit(message.author.id, is_admin=True)
                if is_limited:
                    await message.reply(f"⏳ **Rate limit reached**: Please wait **{wait_sec}s** before asking another question, sir.", mention_author=False)
                    return

                async with message.channel.typing():
                    session_id = f"discord_{message.channel.id}_{message.author.id}"
                    response = await generate_ai_response(
                        prompt=prompt,
                        user_name=message.author.display_name,
                        session_id=session_id,
                        image_data=image_data
                    )
                    chunks = split_message(response, max_length=1950)
                    for chunk in chunks:
                        await message.reply(chunk, mention_author=False)
                return

        await bot.process_commands(message)

    # --- Welcome System State ---
    custom_welcome_channels = {}  # guild_id -> channel_id

    @bot.event
    async def on_member_join(member: discord.Member):
        """Greet new members when they join the server and handle invite roles."""
        guild = member.guild

        # Check if joined via a tracked invite link
        used_invite_code = None
        try:
            current_invites = await guild.invites()
            old_invites = guild_invites_cache.get(guild.id, {})
            for inv in current_invites:
                if inv.code in old_invites:
                    if inv.uses > old_invites[inv.code]:
                        used_invite_code = inv.code
                        break
                elif inv.uses > 0:
                    used_invite_code = inv.code
                    break
            guild_invites_cache[guild.id] = {inv.code: inv.uses for inv in current_invites}
        except Exception:
            pass

        assigned_invite_role = None
        if used_invite_code:
            role_id = get_invite_role(guild.id, used_invite_code)
            if role_id:
                auto_role = guild.get_role(role_id)
                if auto_role and auto_role < guild.me.top_role:
                    try:
                        await member.add_roles(auto_role, reason=f"Auto-assigned via invite link {used_invite_code}")
                        assigned_invite_role = auto_role
                        print(f"✅ Auto-assigned {auto_role.name} to {member} via invite link {used_invite_code}")
                    except Exception as e:
                        print(f"⚠️ Failed to auto-assign invite role: {e}")

        # 1. Determine the appropriate welcome channel
        welcome_channel = None
        if guild.id in custom_welcome_channels:
            welcome_channel = guild.get_channel(custom_welcome_channels[guild.id])

        if not welcome_channel:
            welcome_channel = guild.system_channel

        if not welcome_channel:
            for name in ["welcome", "welcome-and-rules", "general", "lounge", "lobby"]:
                ch = discord.utils.find(lambda c: c.name.lower() == name, guild.text_channels)
                if ch:
                    welcome_channel = ch
                    break

        if welcome_channel:
            embed = discord.Embed(
                title=f"👋 Welcome to {guild.name}!",
                description=(
                    f"Greetings, {member.mention}! I am **J.A.R.V.I.S.**, the resident AI assistant.\n"
                    f"We are delighted to welcome you to our community."
                ),
                color=discord.Color.gold()
            )
            if member.display_avatar:
                embed.set_thumbnail(url=member.display_avatar.url)

            rules_ch = discord.utils.find(lambda c: "rule" in c.name.lower(), guild.text_channels)
            if rules_ch:
                embed.add_field(name="📜 Server Rules", value=f"Please review {rules_ch.mention} to get started.", inline=True)

            embed.add_field(name="🤖 AI Assistant", value="Admin-only AI assistant available via `/ask` or mentioning `@Jarvis`.", inline=True)
            embed.add_field(name="👥 Member Count", value=f"You are member **#{guild.member_count}**", inline=False)
            embed.set_footer(text="J.A.R.V.I.S. Protocol • Welcome System")

            try:
                await welcome_channel.send(content=f"Welcome {member.mention}!", embed=embed)
            except Exception as e:
                print(f"⚠️ Failed to send welcome message in {guild.name}: {e}")

        # 2. Optionally send a polite welcome direct message (DM)
        try:
            dm_embed = discord.Embed(
                title=f"Welcome to {guild.name}!",
                description=(
                    f"Hello {member.name}, welcome to **{guild.name}**!\n\n"
                    f"I'm **J.A.R.V.I.S.**, the resident server assistant. If you need any help, please consult the server staff.\n\n"
                    f"Enjoy your stay!"
                ),
                color=discord.Color.blue()
            )
            await member.send(embed=dm_embed)
        except (discord.Forbidden, discord.HTTPException):
            pass  # Member has DMs disabled

    # ==================== GENERAL COMMANDS ====================

    @bot.hybrid_command(name='help', description="Show the Discord bot help menu")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def discord_help(ctx):
        embed = discord.Embed(
            title="📚 Discord Bot Help Menu",
            description="All commands work with both `/command` (Slash) and `!command` (Prefix):",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="🧠 AI Assistant (J.A.R.V.I.S.) — [Admin Only]",
            value=(
                "`/ask <prompt> [image]` - Ask Jarvis AI anything (supports vision & memory)\n"
                "`/ai <prompt>` - Alias for `/ask`\n"
                "`/reset` - Clear conversation memory\n"
                "`@Jarvis <prompt>` - Mention Jarvis anywhere to chat directly\n"
                "**DMs**: Direct message Jarvis for continuous 1-on-1 conversations\n"
                "**Apps**: Right-click any message -> Apps -> **Explain with Jarvis**\n"
                "*Note: AI cognitive features are restricted to Server Administrators.*"
            ),
            inline=False
        )
        embed.add_field(
            name="🤖 General",
            value=(
                "`/help` or `!help` - Show this menu\n"
                "`/hello` or `!hello` - Friendly greeting\n"
                "`/echo <text>` - Repeat your message\n"
                "`/ping` or `!ping` - Latency check\n"
                "`/info` or `!info` - Bot information\n"
                "`/status` or `!status` - Bot operational status"
            ),
            inline=False
        )
        embed.add_field(
            name="🛡️ Role Management (Requires Manage Roles)",
            value=(
                "`/giverole @user <role>` - Assign a role to a member\n"
                "`/removerole @user <role>` - Remove a role from a member\n"
                "`/createrole <name> [color]` - Create a new role (e.g. `/createrole Gamer #ff0000`)\n"
                "`/roles` - List all server roles and member counts\n"
                "`/claimrole @role [options]` - Create a 1-click button embed for members to claim a role\n"
                "`/claimlink @role [member]` - Generate a web link for members to claim a role\n"
                "`/inviterole @role [channel]` - Create a Discord invite that auto-assigns a role\n"
                "`/rolemenu <title> <@role1> [@role2...]` - Create an interactive self-role button panel"
            ),
            inline=False
        )
        embed.add_field(
            name="📁 Channel Management (Requires Manage Channels)",
            value=(
                "`/createchannel <name> [type] [category]` - Create a channel\n"
                "`/createmultichannel <layout>` - Bulk create channels across categories\n"
                "`/deletechannel [#channel]` - Delete a channel (defaults to current)\n"
                "`/createcategory <name>` - Create a new category"
            ),
            inline=False
        )
        embed.add_field(
            name="📜 Rules & Server Setup (Requires Admin)",
            value=(
                "`/rules [#channel]` - Post a sleek pre-configured rules embed\n"
                "`/postrules <Title> | <Rule 1> | <Rule 2>...` - Post custom rules\n"
                "`/setup_server` - One-click server setup (channels, categories, roles)\n"
                "`/setwelcome [#channel]` - Set channel for new member greetings\n"
                "`/testwelcome [@user]` - Preview the welcome greeting"
            ),
            inline=False
        )
        embed.add_field(
            name="🎮 Presence Management (Requires Admin)",
            value=(
                "`/setpresence <type> <name> [| state]` - Set custom bot activity\n"
                "`/resetpresence` - Reset activity to Competitive (Playing Solo)"
            ),
            inline=False
        )
        embed.add_field(
            name="🏆 Leveling & XP System",
            value=(
                "`/rank [@user]` - View Text & Voice rank, level, and progress bar card\n"
                "`/leaderboard [page] [sort_by]` - View server rankings with medals (🥇🥈🥉)"
            ),
            inline=False
        )
        embed.add_field(
            name="🛡️ AutoMod & Moderation (Staff / Admin)",
            value=(
                "`/warn @user [reason]` - Issue a warning and send an AutoMod alert DM\n"
                "`/warnings [@user]` - View member or server warning history\n"
                "`/strikes [@user]` - View member strike count and current sanction tier\n"
                "`/untimeout @user [reason]` - Cancel/remove an active timeout\n"
                "`/unban <user_id> [reason]` - Cancel/reverse a temporary or permanent ban\n"
                "`/clearstrikes @user` - Reset and clear all strikes for a member\n"
                "`/automod [rule] [enabled]` - View or toggle filters (`anticaps`, `antiinvites`, `massmentions`, `antispam`, `badwords`)\n"
                "`/badwords <add|remove|list> [word]` - Manage custom server bad words\n"
                "`/setmodlog [#channel]` - Set mod-log channel for AutoMod alerts"
            ),
            inline=False
        )
        embed.set_footer(text="Tip: Ensure the bot's role is positioned high in Server Settings > Roles!")
        await ctx.send(embed=embed)

    @bot.hybrid_command(name='hello', description="Friendly greeting")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def discord_hello(ctx):
        await ctx.send(f'👋 Hello {ctx.author.mention}! Ready to customize your server? Type `/help` to see commands.')

    @bot.hybrid_command(name='echo', description="Repeat your message")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def discord_echo(ctx, *, text: str):
        await ctx.send(f'🔊 Echo: {text}')

    @bot.hybrid_command(name='ping', description="Check bot latency")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def discord_ping(ctx):
        latency = round(bot.latency * 1000)
        await ctx.send(f'🏓 Pong! Latency: {latency}ms')

    @bot.hybrid_command(name='info', description="Show bot information and stats")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def discord_info(ctx):
        embed = discord.Embed(title="🤖 Combined Bot Info", color=discord.Color.teal())
        embed.add_field(name="Platform", value="Telegram + Discord", inline=True)
        embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="Servers", value=str(len(bot.guilds)), inline=True)
        embed.add_field(name="Total Users", value=str(len(set(bot.get_all_members()))), inline=True)
        await ctx.send(embed=embed)

    @bot.hybrid_command(name='status', description="Show bot operational status")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def discord_status(ctx):
        status_text = "✅ **Bot Status**\n"
        status_text += "Discord: Online 🟢\n"
        if bot.activity:
            act_type = bot.activity.type.name.capitalize()
            act_name = getattr(bot.activity, "name", "")
            act_state = getattr(bot.activity, "state", "")
            status_text += f"Activity: {act_type} {act_name}"
            if act_state:
                status_text += f" ({act_state})"
            status_text += "\n"
        status_text += "Telegram: Check your chat 💬\n"
        status_text += "Prefix: `/` (Slash) or `!`\n"
        status_text += "AI Assistant: " + ("Online 🟢" if GEMINI_API_KEY else "Offline (Set GEMINI_API_KEY) ⚪") + "\n"
        status_text += "Use `/help` for commands"
        await ctx.send(status_text)

    # ==================== AI ASSISTANT (J.A.R.V.I.S.) ====================

    @bot.hybrid_command(name='ask', aliases=['ai'], description="Ask Jarvis AI anything (Admin only)")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def discord_ask(ctx, prompt: str, image: Optional[discord.Attachment] = None):
        """Ask Jarvis AI anything (Admin only).
        Usage:
          /ask prompt: What is the speed of light?
          /ask prompt: Explain this code image: [Upload Image]
        """
        if not await is_admin_user(ctx.author, ctx.guild):
            await ctx.send("⛔ **Access Denied**: J.A.R.V.I.S. AI cognitive systems are restricted to server administrators only, sir.", ephemeral=True)
            return

        is_limited, wait_sec = check_ai_rate_limit(ctx.author.id, is_admin=True)
        if is_limited:
            await ctx.send(f"⏳ **Rate limit reached**: Please wait **{wait_sec}s** before asking another question, sir.", ephemeral=True)
            return

        await ctx.defer()
        user_name = ctx.author.display_name
        session_id = f"discord_{ctx.channel.id}_{ctx.author.id}" if ctx.guild else f"discord_dm_{ctx.author.id}"

        image_data = None
        if image:
            if image.content_type and image.content_type.startswith("image/"):
                try:
                    data = await image.read()
                    image_data = (data, image.content_type)
                except Exception as e:
                    await ctx.send(f"⚠️ Failed to read image attachment: `{e}`")
                    return
            else:
                await ctx.send("⚠️ Please provide a valid image file (PNG, JPEG, WEBP, GIF).")
                return

        response = await generate_ai_response(
            prompt=prompt,
            user_name=user_name,
            session_id=session_id,
            image_data=image_data
        )
        chunks = split_message(response, max_length=1950)
        for chunk in chunks:
            await ctx.send(chunk)

    @bot.hybrid_command(name='reset', description="Clear conversation memory with Jarvis (Admin only)")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def discord_reset(ctx):
        """Clear conversation memory with Jarvis (Admin only).
        Usage: /reset
        """
        if not await is_admin_user(ctx.author, ctx.guild):
            await ctx.send("⛔ **Access Denied**: J.A.R.V.I.S. AI cognitive systems are restricted to server administrators only, sir.", ephemeral=True)
            return

        session_id = f"discord_{ctx.channel.id}_{ctx.author.id}" if ctx.guild else f"discord_dm_{ctx.author.id}"
        clear_session_history(session_id)
        await ctx.send("🧹 Memory cleared! I am ready for a fresh conversation, sir.")

    @bot.tree.context_menu(name="Explain with Jarvis")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def explain_with_jarvis(interaction: discord.Interaction, message: discord.Message):
        """Context menu app: Right-click any message -> Apps -> Explain with Jarvis (Admin only)."""
        if not await is_admin_user(interaction.user, interaction.guild):
            await interaction.response.send_message("⛔ **Access Denied**: J.A.R.V.I.S. AI cognitive systems are restricted to server administrators only, sir.", ephemeral=True)
            return

        is_limited, wait_sec = check_ai_rate_limit(interaction.user.id, is_admin=True)
        if is_limited:
            await interaction.response.send_message(f"⏳ **Rate limit reached**: Please wait **{wait_sec}s** before asking another question, sir.", ephemeral=True)
            return

        await interaction.response.defer()
        target_text = message.clean_content.strip() if message.clean_content else ""

        image_data = None
        if message.attachments:
            for att in message.attachments:
                if att.content_type and att.content_type.startswith("image/"):
                    try:
                        data = await att.read()
                        image_data = (data, att.content_type)
                        break
                    except Exception:
                        pass

        if not target_text and not image_data:
            await interaction.followup.send("⚠️ That message contains no text or image for me to analyze, sir.", ephemeral=True)
            return

        prompt = f"Please explain, summarize, or debug the following message:\n\n\"{target_text}\"" if target_text else "Please analyze this image, sir."
        response = await generate_ai_response(
            prompt=prompt,
            user_name=interaction.user.display_name,
            image_data=image_data
        )
        chunks = split_message(response, max_length=1950)
        for i, chunk in enumerate(chunks):
            if i == 0:
                await interaction.followup.send(chunk)
            else:
                await interaction.followup.send(chunk)

    # ==================== LEVELING & XP SYSTEM ====================

    @bot.hybrid_command(name='rank', description="View your or another user's rank, level, and XP progress")
    @app_commands.describe(member="The member whose rank you want to check (defaults to you)")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def discord_rank(ctx, member: Optional[discord.Member] = None):
        """View rank card with Text and Voice XP progress bars.
        Usage: /rank [@user]
        """
        if not ctx.guild:
            await ctx.send("ℹ️ The ranking system is only active within servers, sir.")
            return

        target_user = member or ctx.author
        if target_user.bot:
            await ctx.send("🤖 Bots do not participate in the leveling system, sir.")
            return

        stats = get_user_level_stats(ctx.guild.id, target_user.id)
        text_bar = make_progress_bar(stats["text_curr"], stats["text_needed"])
        voice_bar = make_progress_bar(stats["voice_curr"], stats["voice_needed"])

        embed = discord.Embed(
            title=f"📊 Rank Card — {target_user.display_name}",
            color=discord.Color.purple()
        )
        if target_user.display_avatar:
            embed.set_thumbnail(url=target_user.display_avatar.url)

        embed.add_field(
            name=f"💬 Text Activity • LVL {stats['text_level']}",
            value=(
                f"**Rank:** `#{stats['text_rank']}` • **Total XP:** `{stats['text_xp']:,}`\n"
                f"{text_bar} `{stats['text_curr']} / {stats['text_needed']} XP`"
            ),
            inline=False
        )

        embed.add_field(
            name=f"🎙️ Voice Activity • LVL {stats['voice_level']}",
            value=(
                f"**Rank:** `#{stats['voice_rank']}` • **Total XP:** `{stats['voice_xp']:,}`\n"
                f"{voice_bar} `{stats['voice_curr']} / {stats['voice_needed']} XP`"
            ),
            inline=False
        )

        embed.set_footer(text=f"Total XP: {stats['total_xp']:,} • Overall Rank: #{stats['total_rank']}")
        await ctx.send(embed=embed)

    @bot.hybrid_command(name='leaderboard', description="View server XP leaderboard")
    @app_commands.describe(
        page="Page number to view (default: 1)",
        sort_by="Sort leaderboard by: total, text, or voice (default: total)"
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def discord_leaderboard(ctx, page: int = 1, sort_by: str = "total"):
        """View server XP leaderboard with rankings, medals, and pagination.
        Usage:
          /leaderboard [page]
          /leaderboard page:2 sort_by:voice
        """
        if not ctx.guild:
            await ctx.send("ℹ️ Leaderboards are only available within servers, sir.")
            return

        valid_sorts = ["total", "text", "voice"]
        if sort_by.lower() not in valid_sorts:
            sort_by = "total"

        entries, current_page, total_pages, total_users = get_guild_leaderboard(
            ctx.guild.id, page=page, per_page=10, sort_by=sort_by
        )

        if not entries:
            await ctx.send("ℹ️ No ranking data available for this server yet. Start chatting or join a voice channel!")
            return

        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        sort_label = sort_by.capitalize()
        embed = discord.Embed(
            title=f"🏆 {ctx.guild.name} Leaderboard",
            description=f"Top 10 users by {sort_label} XP – Page {current_page}/{total_pages}\n\n**Rankings**",
            color=discord.Color.gold()
        )
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)

        ranking_lines = []
        for e in entries:
            rank = e["rank"]
            medal_or_rank = medals.get(rank, f"#{rank}")
            member = ctx.guild.get_member(e["user_id"])
            name = member.display_name if member else f"User {e['user_id']}"
            ranking_lines.append(f"{medal_or_rank} **{name}** - Level {e['level']} ({e['xp']:,} XP)")

        embed.description += "\n" + "\n".join(ranking_lines)
        embed.set_footer(text=f"Use /leaderboard [page] to view other pages • {total_users} total users")
        await ctx.send(embed=embed)

    # ==================== AUTOMOD & MODERATION ====================

    @bot.hybrid_command(name='warn', description="Warn a member and send them an AutoMod alert embed")
    @commands.has_permissions(manage_messages=True)
    @app_commands.describe(
        member="The member to warn",
        reason="Reason for the warning"
    )
    async def discord_warn(ctx, member: discord.Member, *, reason: str = "Rule violation"):
        """Warn a member, record it, and send them the AutoMod alert embed via DM.
        Usage: /warn @user [reason]
        """
        if member.bot:
            await ctx.send("❌ You cannot warn a bot, sir.")
            return
        if member == ctx.author:
            await ctx.send("❌ You cannot warn yourself, sir.")
            return

        # Record warning in database
        warn_id = add_warning(ctx.guild.id, member.id, ctx.author.id, reason)

        # Build and send DM alert matching screenshot
        alert_embed = build_automod_alert_embed(ctx.guild.name, reason)
        dm_sent = False
        try:
            await member.send(embed=alert_embed)
            dm_sent = True
        except Exception:
            pass

        # Log to mod-log channel if present
        modlog_ch = get_modlog_channel(ctx.guild)
        if modlog_ch and modlog_ch != ctx.channel:
            log_embed = discord.Embed(
                title="⚠️ AutoMod Alert: Warn",
                description=f"Action taken on {member.mention} by {ctx.author.mention}",
                color=discord.Color.from_rgb(237, 66, 69)
            )
            log_embed.add_field(name="Reason", value=f"Violation: {reason}", inline=True)
            log_embed.add_field(name="Warning ID", value=f"#{warn_id}", inline=True)
            try:
                await modlog_ch.send(embed=log_embed)
            except Exception:
                pass

        status_suffix = " (DM alert sent)" if dm_sent else " (User has DMs closed)"
        await ctx.send(f"⚠️ Warned {member.mention} for: **{reason}**{status_suffix}")

    @bot.hybrid_command(name='warnings', description="View warning history for a user")
    @commands.has_permissions(manage_messages=True)
    @app_commands.describe(member="Member to check warnings for (defaults to entire server)")
    async def discord_warnings(ctx, member: Optional[discord.Member] = None):
        """View warning records for a user or recent server warnings.
        Usage:
          /warnings @user
          /warnings
        """
        target_id = member.id if member else None
        warn_list = get_warnings(ctx.guild.id, target_id)

        target_name = member.display_name if member else ctx.guild.name
        embed = discord.Embed(
            title=f"📋 Warnings Log — {target_name}",
            color=discord.Color.from_rgb(237, 66, 69)
        )

        if not warn_list:
            embed.description = "✅ No warnings recorded."
            await ctx.send(embed=embed)
            return

        embed.description = f"Total warnings: **{len(warn_list)}**\n"
        for w in warn_list[:10]:
            mod_user = ctx.guild.get_member(w["moderator_id"])
            mod_name = mod_user.display_name if mod_user else f"Mod {w['moderator_id']}"
            t_str = f"<t:{int(w['timestamp'])}:R>"
            warned_user = ctx.guild.get_member(w["user_id"])
            user_label = f" for {warned_user.mention}" if not member and warned_user else ""
            embed.add_field(
                name=f"Warning #{w['id']}{user_label} • by {mod_name}",
                value=f"**Reason:** `{w['reason']}`\n**Date:** {t_str}",
                inline=False
            )

        if len(warn_list) > 10:
            embed.set_footer(text=f"Showing latest 10 of {len(warn_list)} warnings")
        await ctx.send(embed=embed)

    @bot.hybrid_command(name='setmodlog', description="Set the moderation log channel (Admin only)")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(channel="The text channel for mod-logs")
    async def discord_setmodlog(ctx, channel: Optional[discord.TextChannel] = None):
        """Designate the channel for AutoMod and moderation alerts.
        Usage: /setmodlog [#channel]
        """
        target = channel or ctx.channel
        custom_modlog_channels[ctx.guild.id] = target.id
        await ctx.send(f"✅ Moderation log channel set to {target.mention}!")

    @bot.hybrid_command(name='automod', description="View or toggle AutoMod filter rules (Admin only)")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(
        rule="The rule to toggle (anticaps, antiinvites, massmentions, antispam, badwords)",
        enabled="Whether to enable or disable the rule"
    )
    async def discord_automod(ctx, rule: Optional[str] = None, enabled: Optional[bool] = None):
        """View or configure AutoMod rules for this server.
        Usage:
          /automod
          /automod rule:badwords enabled:False
        """
        valid_rules = ["anticaps", "antiinvites", "massmentions", "antispam", "badwords"]
        if rule and enabled is not None:
            clean_rule = rule.lower().replace("-", "").replace("_", "").replace(" ", "")
            if clean_rule not in valid_rules:
                valid_str = ", ".join(f"`{r}`" for r in valid_rules)
                await ctx.send(f"❌ Invalid rule. Choose from: {valid_str}")
                return
            set_automod_setting(ctx.guild.id, clean_rule, enabled)
            status_word = "enabled" if enabled else "disabled"
            await ctx.send(f"✅ AutoMod rule **{clean_rule}** has been **{status_word}**!")
            return

        embed = discord.Embed(
            title=f"🛡️ AutoMod Status — {ctx.guild.name}",
            description="Automated moderation filters and rules:",
            color=discord.Color.from_rgb(237, 66, 69)
        )
        for r in valid_rules:
            is_on = get_automod_setting(ctx.guild.id, r)
            status_emoji = "🟢 Enabled" if is_on else "🔴 Disabled"
            embed.add_field(name=f"`{r}`", value=status_emoji, inline=True)

        modlog_ch = get_modlog_channel(ctx.guild)
        modlog_str = modlog_ch.mention if modlog_ch else "*Not set (use `/setmodlog`)*"
        embed.add_field(name="📜 Mod-Log Channel", value=modlog_str, inline=False)
        embed.set_footer(text="Use /automod rule:<name> enabled:<True|False> to toggle")
        await ctx.send(embed=embed)

    @bot.hybrid_command(name='badwords', description="Manage custom bad words blacklist (Admin only)")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(
        action="Action to perform: add, remove, or list",
        word="The word or phrase to add or remove"
    )
    async def discord_badwords(ctx, action: str = "list", *, word: Optional[str] = None):
        """Manage custom bad words blacklist for AutoMod.
        Usage:
          /badwords action:list
          /badwords action:add word:toxicphrase
          /badwords action:remove word:toxicphrase
        """
        act = action.lower().strip()
        if act == "add":
            if not word:
                await ctx.send("❌ Please specify the word to add: `/badwords action:add word:<word>`")
                return
            success = add_guild_badword(ctx.guild.id, word)
            if success:
                await ctx.send(f"✅ Added `||{word}||` to the server's AutoMod bad words blacklist.")
            else:
                await ctx.send("⚠️ Failed to add bad word.")
        elif act == "remove":
            if not word:
                await ctx.send("❌ Please specify the word to remove: `/badwords action:remove word:<word>`")
                return
            success = remove_guild_badword(ctx.guild.id, word)
            if success:
                await ctx.send(f"✅ Removed `||{word}||` from the server's custom bad words list.")
            else:
                await ctx.send("⚠️ Failed to remove bad word.")
        elif act == "list":
            words = get_guild_badwords(ctx.guild.id)
            custom_count = len(words) - len(DEFAULT_BAD_WORDS)
            embed = discord.Embed(
                title=f"🤬 Bad Words Filter — {ctx.guild.name}",
                description=(
                    f"AutoMod filters **{len(words)}** total bad words:\n"
                    f"• Default filtered words: **{len(DEFAULT_BAD_WORDS)}**\n"
                    f"• Custom server words: **{max(0, custom_count)}**\n\n"
                    "Use `/badwords action:add word:<word>` to add more.\n"
                    "Use `/badwords action:remove word:<word>` to remove."
                ),
                color=discord.Color.from_rgb(237, 66, 69)
            )
            embed.set_footer(text="Profanity filter is active with word-boundary matching.")
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Invalid action. Use `list`, `add`, or `remove`.")

    @bot.hybrid_command(name='untimeout', description="Remove timeout from a member (Admin/Mod only)")
    @commands.has_permissions(moderate_members=True)
    @app_commands.describe(
        member="The member to untimeout",
        reason="Reason for canceling timeout"
    )
    async def discord_untimeout(ctx, member: discord.Member, *, reason: str = "Timeout canceled by moderator"):
        """Cancel an active timeout on a member.
        Usage: /untimeout @user [reason]
        """
        try:
            await member.timeout(None, reason=f"{reason} (by {ctx.author})")
            await ctx.send(f"✅ Successfully canceled timeout for {member.mention}.")
        except Exception as e:
            await ctx.send(f"⚠️ Failed to remove timeout: {e}")

    @bot.hybrid_command(name='unban', description="Unban a user and cancel temporary ban (Admin/Mod only)")
    @commands.has_permissions(ban_members=True)
    @app_commands.describe(
        user_id="The Discord user ID of the banned user",
        reason="Reason for canceling ban"
    )
    async def discord_unban(ctx, user_id: str, *, reason: str = "Ban canceled by administrator"):
        """Cancel a ban and remove any active temporary ban record.
        Usage: /unban <user_id> [reason]
        """
        try:
            uid = int(user_id.strip())
            user = await bot.fetch_user(uid)
            await ctx.guild.unban(user, reason=f"{reason} (by {ctx.author})")
            remove_temp_ban(ctx.guild.id, uid)
            await ctx.send(f"✅ Successfully unbanned **{user.name}** (`{uid}`).")
        except ValueError:
            await ctx.send("❌ Please provide a valid numeric User ID.")
        except Exception as e:
            await ctx.send(f"⚠️ Failed to unban: {e}")

    @bot.hybrid_command(name='clearstrikes', description="Clear all AutoMod strikes for a member (Admin only)")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(member="Member to reset strikes for")
    async def discord_clearstrikes(ctx, member: discord.Member):
        """Reset and clear all strikes/warnings for a member.
        Usage: /clearstrikes @user
        """
        cleared = clear_user_strikes(ctx.guild.id, member.id)
        # Also remove timeout if currently timed out
        try:
            if member.is_timed_out():
                await member.timeout(None, reason=f"Strikes cleared by {ctx.author}")
        except Exception:
            pass
        await ctx.send(f"✅ Cleared **{cleared}** strike(s) for {member.mention}. Their record is now clean.")

    @bot.hybrid_command(name='strikes', description="View a member's strike count and active sanction tier")
    @commands.has_permissions(manage_messages=True)
    @app_commands.describe(member="Member to check strikes for")
    async def discord_strikes(ctx, member: Optional[discord.Member] = None):
        """View strike count, punishment status, and warning history.
        Usage: /strikes [@user]
        """
        target = member or ctx.author
        strikes = get_user_strikes(ctx.guild.id, target.id)
        warn_list = get_warnings(ctx.guild.id, target.id)

        if strikes >= 5:
            tier_status = "⛔ Tier 3: 24-Hour Temp Ban (5+ Strikes)"
        elif strikes >= 3:
            tier_status = "⏳ Tier 2: 10-Minute Timeout (3-4 Strikes)"
        else:
            tier_status = "⚠️ Tier 1: Warning Only (< 3 Strikes)"

        embed = discord.Embed(
            title=f"⚖️ Strikes & Moderation Status — {target.display_name}",
            color=discord.Color.from_rgb(237, 66, 69)
        )
        if target.display_avatar:
            embed.set_thumbnail(url=target.display_avatar.url)

        embed.add_field(name="Total Strikes", value=f"**{strikes}** / 5", inline=True)
        embed.add_field(name="Current Sanction Tier", value=tier_status, inline=False)
        embed.add_field(
            name="Sanction Rules",
            value="• **3 Strikes** $\\rightarrow$ 10-Minute Timeout\n• **5 Strikes** $\\rightarrow$ 24-Hour Temporary Ban\n*(Admins can cancel via `/untimeout`, `/unban`, `/clearstrikes`)*",
            inline=False
        )

        if warn_list:
            history_lines = []
            for w in warn_list[:5]:
                t_str = f"<t:{int(w['timestamp'])}:R>"
                history_lines.append(f"• `#{w['id']}` `{w['reason']}` ({t_str})")
            embed.add_field(name="Recent Warnings", value="\n".join(history_lines), inline=False)

        await ctx.send(embed=embed)

    # ==================== PRESENCE MANAGEMENT ====================

    @bot.hybrid_command(name='setpresence', description="Dynamically update bot presence (Admin only)")
    @commands.has_permissions(administrator=True)
    async def discord_setpresence(ctx, activity_type: str, *, text: str):
        """
        Dynamically update bot presence.
        Usage:
          /setpresence competing Competitive | Playing Solo
          /setpresence playing Overwatch 2
          /setpresence watching Tournaments
          /setpresence listening Chill Beats
        """
        parts = [p.strip() for p in text.split('|', 1)]
        name = parts[0]
        state = parts[1] if len(parts) > 1 else None

        type_map = {
            'playing': discord.ActivityType.playing,
            'streaming': discord.ActivityType.streaming,
            'listening': discord.ActivityType.listening,
            'watching': discord.ActivityType.watching,
            'competing': discord.ActivityType.competing,
            'custom': discord.ActivityType.custom,
        }

        act_type = type_map.get(activity_type.lower())
        if act_type is None:
            valid = ", ".join(f"`{k}`" for k in type_map.keys())
            await ctx.send(f"❌ Invalid activity type. Valid types: {valid}")
            return

        activity = discord.Activity(type=act_type, name=name, state=state)
        await bot.change_presence(activity=activity)

        embed = discord.Embed(title="🎮 Presence Updated", color=discord.Color.green())
        embed.add_field(name="Type", value=activity_type.capitalize(), inline=True)
        embed.add_field(name="Name", value=name, inline=True)
        if state:
            embed.add_field(name="State", value=state, inline=True)
        await ctx.send(embed=embed)

    @bot.hybrid_command(name='resetpresence', description="Reset presence to default (Admin only)")
    @commands.has_permissions(administrator=True)
    async def discord_resetpresence(ctx):
        """Reset bot presence to default (Competitive | Playing Solo)."""
        activity = discord.Activity(
            type=discord.ActivityType.competing,
            name="Competitive",
            state="Playing Solo"
        )
        await bot.change_presence(activity=activity)
        await ctx.send("✅ Presence reset to default: **Competing in Competitive (Playing Solo)**.")

    # ==================== ROLE MANAGEMENT ====================

    @bot.hybrid_command(name='giverole', description="Assign an existing role to a member")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def discord_giverole(ctx, member: discord.Member, role: discord.Role):
        """Assign an existing role to a member."""
        if role >= ctx.guild.me.top_role:
            await ctx.send("❌ I cannot assign that role because it is higher than or equal to my highest role!")
            return
        if role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send("❌ You cannot assign a role that is higher than or equal to your own highest role!")
            return
        if role in member.roles:
            await ctx.send(f"ℹ️ {member.mention} already has the **{role.name}** role.")
            return

        await member.add_roles(role, reason=f"Given by {ctx.author}")
        embed = discord.Embed(
            title="✅ Role Assigned",
            description=f"Successfully added **{role.name}** to {member.mention}.",
            color=role.color if role.color.value != 0 else discord.Color.green()
        )
        await ctx.send(embed=embed)

    @bot.hybrid_command(name='removerole', description="Remove a role from a member")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def discord_removerole(ctx, member: discord.Member, role: discord.Role):
        """Remove a role from a member."""
        if role >= ctx.guild.me.top_role:
            await ctx.send("❌ I cannot remove that role because it is higher than or equal to my highest role!")
            return
        if role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send("❌ You cannot remove a role that is higher than or equal to your own highest role!")
            return
        if role not in member.roles:
            await ctx.send(f"ℹ️ {member.mention} does not have the **{role.name}** role.")
            return

        await member.remove_roles(role, reason=f"Removed by {ctx.author}")
        embed = discord.Embed(
            title="✅ Role Removed",
            description=f"Successfully removed **{role.name}** from {member.mention}.",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)

    @bot.hybrid_command(name='createrole', description="Create a new role with optional hex color")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def discord_createrole(ctx, name: str, color: Optional[str] = None):
        """Create a new role with an optional hex color (e.g. /createrole Gamer #ff0000)."""
        role_color = discord.Color.default()
        if color:
            clean_color = color.lstrip('#')
            try:
                role_color = discord.Color(int(clean_color, 16))
            except ValueError:
                await ctx.send("⚠️ Invalid hex color code. Creating role with default color instead.")

        new_role = await ctx.guild.create_role(
            name=name,
            color=role_color,
            reason=f"Created by {ctx.author}"
        )
        embed = discord.Embed(
            title="✅ Role Created",
            description=f"Role **{new_role.name}** was created successfully.",
            color=new_role.color if new_role.color.value != 0 else discord.Color.green()
        )
        embed.add_field(name="Role ID", value=f"`{new_role.id}`", inline=True)
        embed.add_field(name="Color", value=f"`{str(new_role.color)}`", inline=True)
        await ctx.send(embed=embed)

    @bot.hybrid_command(name='roles', description="List all server roles and their member counts")
    async def discord_roles(ctx):
        """List all server roles and their member counts."""
        roles = [r for r in ctx.guild.roles if not r.is_default()]
        roles.reverse()  # Highest hierarchy first

        if not roles:
            await ctx.send("ℹ️ No custom roles found in this server.")
            return

        lines = [f"• **{role.name}** ({len(role.members)} members) - `{role.id}`" for role in roles[:30]]
        embed = discord.Embed(
            title=f"🛡️ Server Roles ({len(roles)} total)",
            description="\n".join(lines),
            color=discord.Color.blurple()
        )
        if len(roles) > 30:
            embed.set_footer(text=f"Showing top 30 of {len(roles)} roles")
        await ctx.send(embed=embed)

    @bot.hybrid_command(name='rolemenu', description="Create an interactive self-role button panel")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def discord_rolemenu(
        ctx,
        title: str,
        role1: discord.Role,
        role2: Optional[discord.Role] = None,
        role3: Optional[discord.Role] = None,
        role4: Optional[discord.Role] = None,
        role5: Optional[discord.Role] = None
    ):
        """Create an interactive button menu for self-assignable roles.
        Usage: /rolemenu "Pick Your Roles" @Gamer @Developer
        """
        roles = [r for r in [role1, role2, role3, role4, role5] if r is not None]
        if not roles:
            await ctx.send("⚠️ Please specify at least one role.")
            return

        # Check bot hierarchy for all roles
        unassignable = [r.name for r in roles if r >= ctx.guild.me.top_role]
        if unassignable:
            await ctx.send(f"❌ I cannot manage these roles because they are higher than or equal to my highest role: {', '.join(unassignable)}")
            return

        view = SelfRoleView(roles)
        embed = discord.Embed(
            title=f"🎭 {title}",
            description="Click the buttons below to add or remove roles from yourself!",
            color=discord.Color.gold()
        )
        embed.set_footer(text="Click once to get the role, click again to remove it.")
        await ctx.send(embed=embed, view=view)

    @bot.hybrid_command(
        name='claimrole',
        aliases=['rolebutton', 'buttonrole'],
        description="Create an interactive 1-click button for members to claim a role"
    )
    @app_commands.describe(
        role="The role to give when clicked",
        title="Custom title for the embed card",
        description="Custom message describing the role",
        button_label="Label text on the button",
        button_color="Color style: green, blue, grey, red (default: green)",
        emoji="Emoji to display on the button (e.g. ✅, 🔗, ⭐)",
        toggle="Allow clicking again to remove role (default: False)",
        channel="Channel to post into (defaults to current channel)"
    )
    @app_commands.choices(button_color=[
        app_commands.Choice(name="Green (Success)", value="green"),
        app_commands.Choice(name="Blue (Primary)", value="blue"),
        app_commands.Choice(name="Grey (Secondary)", value="grey"),
        app_commands.Choice(name="Red (Danger)", value="red"),
    ])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def discord_claimrole(
        ctx,
        role: discord.Role,
        title: Optional[str] = None,
        description: Optional[str] = None,
        button_label: Optional[str] = None,
        button_color: str = "green",
        emoji: Optional[str] = "✅",
        toggle: bool = False,
        channel: Optional[discord.TextChannel] = None
    ):
        """Create a clickable button embed to give users a role when clicked.
        Usage:
          /claimrole @Member
          /claimrole role:@VIP title:"VIP Access" description:"Click to claim your VIP access!" button_label:"Claim VIP" emoji:⭐ button_color:green
        """
        if not ctx.guild:
            await ctx.send("❌ This command can only be used within a server.")
            return

        if role >= ctx.guild.me.top_role:
            await ctx.send("❌ I cannot assign that role because it is higher than or equal to my highest role in Server Settings > Roles!")
            return

        if role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send("❌ You cannot assign a role that is higher than or equal to your own highest role!")
            return

        target_channel = channel or ctx.channel

        color_map = {
            "green": discord.ButtonStyle.success,
            "blue": discord.ButtonStyle.primary,
            "grey": discord.ButtonStyle.secondary,
            "gray": discord.ButtonStyle.secondary,
            "red": discord.ButtonStyle.danger
        }
        btn_style = color_map.get(button_color.lower(), discord.ButtonStyle.success)

        clean_emoji = emoji.strip() if emoji and emoji.strip() else None

        btn = ClaimRoleButton(
            role_id=role.id,
            toggle=toggle,
            label=button_label or f"Claim {role.name}",
            style=btn_style,
            emoji=clean_emoji
        )

        view = discord.ui.View(timeout=None)
        view.add_item(btn)

        embed = discord.Embed(
            title=f"🎭 {title or f'Claim Role: {role.name}'}",
            description=description or f"Click the button below to receive the **{role.name}** role!",
            color=role.color if role.color.value != 0 else discord.Color.green()
        )
        footer_text = f"Role: {role.name} • Click the button below"
        if toggle:
            footer_text += " (Click again to remove)"
        embed.set_footer(text=footer_text)

        if target_channel != ctx.channel:
            await target_channel.send(embed=embed, view=view)
            await ctx.send(f"✅ Claim role button successfully posted in {target_channel.mention}!", ephemeral=True)
        else:
            await ctx.send(embed=embed, view=view)

    @bot.hybrid_command(
        name='claimlink',
        aliases=['createrolelink', 'rolelink'],
        description="Generate a web link that gives users a role when accessed (Manage Roles)"
    )
    @app_commands.describe(
        role="The role to give when link is accessed",
        member="Specific member this link is for (optional, leave blank for open link)",
        max_uses="Maximum number of times this link can be claimed (default: 1)",
        expires_hours="Hours until link expires (default: 24, 0 for no expiration)"
    )
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def discord_claimlink(
        ctx,
        role: discord.Role,
        member: Optional[discord.Member] = None,
        max_uses: int = 1,
        expires_hours: float = 24.0
    ):
        """Generate a web link that gives users a role when clicked in a browser.
        Usage:
          /claimlink @VIP
          /claimlink role:@VIP member:@User max_uses:1 expires_hours:48
        """
        if not ctx.guild:
            await ctx.send("❌ This command can only be used within a server.")
            return

        if role >= ctx.guild.me.top_role:
            await ctx.send("❌ I cannot assign that role because it is higher than or equal to my highest role in Server Settings > Roles!")
            return

        if role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send("❌ You cannot assign a role that is higher than or equal to your own highest role!")
            return

        exp = expires_hours if expires_hours > 0 else None
        target_uid = member.id if member else None

        token = create_role_claim_link(
            guild_id=ctx.guild.id,
            role_id=role.id,
            created_by=ctx.author.id,
            target_user_id=target_uid,
            max_uses=max(1, max_uses),
            expires_hours=exp
        )

        if not token:
            await ctx.send("❌ Failed to generate claim link.")
            return

        link_url = f"{CLAIM_SERVER_BASE_URL}/claim?token={token}"

        embed = discord.Embed(
            title="🔗 Role Claim Link Generated",
            description=f"Accessing this link will grant the **{role.name}** role!",
            color=role.color if role.color.value != 0 else discord.Color.green()
        )
        embed.add_field(name="🌐 Claim URL", value=f"[👉 Click Here to Claim Role]({link_url})\n`{link_url}`", inline=False)
        embed.add_field(name="🛡️ Role", value=role.mention, inline=True)
        if member:
            embed.add_field(name="👤 Assigned To", value=member.mention, inline=True)
        else:
            embed.add_field(name="👥 Max Claims", value=f"{max_uses} use(s)", inline=True)

        exp_text = f"{expires_hours} hours" if exp else "Never"
        embed.add_field(name="⏳ Expiration", value=exp_text, inline=True)
        embed.set_footer(text="Tip: You can send this link anywhere (DMs, website, email) for users to claim their role!")

        await ctx.send(embed=embed, ephemeral=True)

    @bot.hybrid_command(
        name='inviterole',
        aliases=['roleinvite'],
        description="Create a Discord invite that automatically grants a role to anyone who joins with it"
    )
    @app_commands.describe(
        role="The role to automatically grant when someone joins using this invite",
        channel="Channel the invite should lead to (defaults to current channel)",
        max_uses="Maximum uses (0 for unlimited, default: 0)",
        max_age_hours="Hours until invite expires (0 for never, default: 0)"
    )
    @commands.has_permissions(manage_roles=True, create_instant_invite=True)
    @commands.bot_has_permissions(manage_roles=True, create_instant_invite=True)
    async def discord_inviterole(
        ctx,
        role: discord.Role,
        channel: Optional[discord.TextChannel] = None,
        max_uses: int = 0,
        max_age_hours: float = 0.0
    ):
        """Create a Discord invite link that automatically grants a role to anyone who joins with it.
        Usage:
          /inviterole @Member
          /inviterole role:@VIP channel:#welcome max_uses:10 max_age_hours:48
        """
        if not ctx.guild:
            await ctx.send("❌ This command can only be used within a server.")
            return

        if role >= ctx.guild.me.top_role:
            await ctx.send("❌ I cannot assign that role because it is higher than or equal to my highest role in Server Settings > Roles!")
            return

        if role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send("❌ You cannot assign a role that is higher than or equal to your own highest role!")
            return

        target_ch = channel or ctx.channel
        max_age_sec = int(max_age_hours * 3600) if max_age_hours > 0 else 0

        try:
            invite = await target_ch.create_invite(
                max_age=max_age_sec,
                max_uses=max(0, max_uses),
                unique=True,
                reason=f"Role invite created by {ctx.author} for {role.name}"
            )
        except Exception as e:
            await ctx.send(f"❌ Failed to create invite: `{e}`")
            return

        # Store in SQLite
        add_invite_role(invite.code, ctx.guild.id, role.id, ctx.author.id)

        # Update cache
        if ctx.guild.id not in guild_invites_cache:
            guild_invites_cache[ctx.guild.id] = {}
        guild_invites_cache[ctx.guild.id][invite.code] = 0

        embed = discord.Embed(
            title="🔗 Role Invite Link Created",
            description=f"Anyone who joins using this invite link will automatically be given the **{role.name}** role!",
            color=role.color if role.color.value != 0 else discord.Color.gold()
        )
        embed.add_field(name="📨 Invite Link", value=f"`{invite.url}`\n[👉 Click to Join]({invite.url})", inline=False)
        embed.add_field(name="🛡️ Role", value=role.mention, inline=True)
        embed.add_field(name="📍 Channel", value=target_ch.mention, inline=True)
        embed.add_field(name="👥 Max Uses", value="Unlimited" if max_uses == 0 else str(max_uses), inline=True)
        embed.add_field(name="⏳ Expiration", value="Never" if max_age_hours == 0 else f"{max_age_hours} hours", inline=True)
        embed.set_footer(text="J.A.R.V.I.S. Protocol • Invite Role System")

        await ctx.send(embed=embed)

    # ==================== CHANNEL MANAGEMENT ====================

    def parse_channel_layout_string(layout_str: str) -> List[Dict[str, Any]]:
        """
        Parse a string layout into category and channel specifications.
        Format: "Category1: chan1, chan2, voice:vc1 | Category2: chan3, voice:vc2"
        """
        results = []
        category_blocks = [b.strip() for b in layout_str.split('|') if b.strip()]
        for block in category_blocks:
            if ':' in block:
                cat_name, channels_part = block.split(':', 1)
            elif '>' in block:
                cat_name, channels_part = block.split('>', 1)
            else:
                cat_name, channels_part = block, ""
            cat_name = cat_name.strip()
            channel_items = [ch.strip() for ch in channels_part.split(',') if ch.strip()]
            channels = []
            for ch in channel_items:
                lower_ch = ch.lower()
                if lower_ch.startswith("voice:"):
                    channels.append({"name": ch[6:].strip(), "type": "voice"})
                elif lower_ch.startswith("vc:"):
                    channels.append({"name": ch[3:].strip(), "type": "voice"})
                elif lower_ch.startswith("text:"):
                    channels.append({"name": ch[5:].strip().lstrip('#'), "type": "text"})
                else:
                    channels.append({"name": ch.lstrip('#').strip(), "type": "text"})
            results.append({"category": cat_name, "channels": channels})
        return results

    def normalize_channel_structure(structure: Union[str, Dict[str, Any], List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Normalizes various structure formats into:
        [{"category": "Name", "channels": [{"name": "ch1", "type": "text"}, ...]}, ...]
        """
        if isinstance(structure, str):
            return parse_channel_layout_string(structure)
        normalized = []
        if isinstance(structure, dict):
            for cat_name, val in structure.items():
                channels = []
                if isinstance(val, list):
                    for item in val:
                        if isinstance(item, str):
                            lower_item = item.lower()
                            if lower_item.startswith("voice:"):
                                channels.append({"name": item[6:].strip(), "type": "voice"})
                            elif lower_item.startswith("vc:"):
                                channels.append({"name": item[3:].strip(), "type": "voice"})
                            elif lower_item.startswith("text:"):
                                channels.append({"name": item[5:].strip().lstrip('#'), "type": "text"})
                            else:
                                channels.append({"name": item.lstrip('#').strip(), "type": "text"})
                        elif isinstance(item, dict):
                            channels.append({
                                "name": item.get("name", "").strip(),
                                "type": item.get("type", "text").lower()
                            })
                elif isinstance(val, dict):
                    for text_ch in val.get("text", []):
                        channels.append({"name": str(text_ch).lstrip('#').strip(), "type": "text"})
                    for voice_ch in val.get("voice", []):
                        channels.append({"name": str(voice_ch).strip(), "type": "voice"})
                normalized.append({"category": str(cat_name).strip(), "channels": channels})
        elif isinstance(structure, list):
            for entry in structure:
                if isinstance(entry, dict):
                    cat_name = entry.get("category", "").strip()
                    channels = []
                    if "channels" in entry and isinstance(entry["channels"], list):
                        for item in entry["channels"]:
                            if isinstance(item, str):
                                lower_item = item.lower()
                                if lower_item.startswith("voice:"):
                                    channels.append({"name": item[6:].strip(), "type": "voice"})
                                elif lower_item.startswith("vc:"):
                                    channels.append({"name": item[3:].strip(), "type": "voice"})
                                else:
                                    channels.append({"name": item.lstrip('#').strip(), "type": "text"})
                            elif isinstance(item, dict):
                                channels.append({
                                    "name": item.get("name", "").strip(),
                                    "type": item.get("type", "text").lower()
                                })
                    else:
                        for text_ch in entry.get("text", []):
                            channels.append({"name": str(text_ch).lstrip('#').strip(), "type": "text"})
                        for voice_ch in entry.get("voice", []):
                            channels.append({"name": str(voice_ch).strip(), "type": "voice"})
                    normalized.append({"category": cat_name, "channels": channels})
        return normalized

    async def create_multiple_channels(
        guild: discord.Guild,
        structure: Union[str, Dict[str, Any], List[Dict[str, Any]]],
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates multiple channels organized across categories in a Discord server.

        Parameters:
        - guild (discord.Guild): Target Discord server.
        - structure (Union[str, dict, list]): Layout of categories and channels.
            Formats supported:
            1. Shorthand string: "Category1: ch1, voice:vc1 | Category2: ch2"
            2. Dict with list: {"Category1": ["ch1", "voice:vc1"], "Category2": ["ch2"]}
            3. Dict with type dict: {"Category1": {"text": ["ch1"], "voice": ["vc1"]}}
            4. List of dicts: [{"category": "Category1", "text": ["ch1"], "voice": ["vc1"]}]
        - reason (Optional[str]): Audit log reason.

        Returns:
            dict containing:
            - categories_created: list of newly created CategoryChannel
            - categories_reused: list of existing CategoryChannel reused
            - channels_created: list of newly created TextChannel or VoiceChannel
            - skipped: list of dicts for skipped existing channels
            - errors: list of dicts for any errors encountered
        """
        audit_reason = reason or "Bulk channel creation"
        categories_created = []
        categories_reused = []
        channels_created = []
        skipped = []
        errors = []

        normalized = normalize_channel_structure(structure)

        for cat_info in normalized:
            cat_name = cat_info.get("category", "").strip()
            channels = cat_info.get("channels", [])
            category = None

            if cat_name:
                category = discord.utils.find(lambda c: c.name.lower() == cat_name.lower(), guild.categories)
                if not category:
                    try:
                        category = await guild.create_category(name=cat_name, reason=audit_reason)
                        categories_created.append(category)
                        await asyncio.sleep(0.3)
                    except Exception as e:
                        errors.append({"target": f"Category '{cat_name}'", "error": str(e)})
                        continue
                else:
                    if category not in categories_reused and category not in categories_created:
                        categories_reused.append(category)

            for ch_spec in channels:
                ch_name = ch_spec.get("name", "").strip()
                ch_type = ch_spec.get("type", "text").lower()
                if not ch_name:
                    continue

                if ch_type in ["voice", "vc"]:
                    existing_vc = None
                    if category:
                        existing_vc = discord.utils.find(lambda c: c.name.lower() == ch_name.lower(), category.voice_channels)
                    else:
                        existing_vc = discord.utils.find(lambda c: c.name.lower() == ch_name.lower() and c.category is None, guild.voice_channels)

                    if existing_vc:
                        skipped.append({
                            "category": category.name if category else "None",
                            "channel": ch_name,
                            "type": "voice",
                            "reason": "Voice channel already exists"
                        })
                    else:
                        try:
                            new_vc = await guild.create_voice_channel(name=ch_name, category=category, reason=audit_reason)
                            channels_created.append(new_vc)
                            await asyncio.sleep(0.3)
                        except Exception as e:
                            errors.append({"target": f"Voice channel '{ch_name}' in '{category.name if category else 'None'}'", "error": str(e)})

                else:
                    clean_ch_name = ch_name.lower().replace(" ", "-")
                    existing_tc = None
                    if category:
                        existing_tc = discord.utils.find(lambda c: c.name.lower() == clean_ch_name, category.text_channels)
                    else:
                        existing_tc = discord.utils.find(lambda c: c.name.lower() == clean_ch_name and c.category is None, guild.text_channels)

                    if existing_tc:
                        skipped.append({
                            "category": category.name if category else "None",
                            "channel": clean_ch_name,
                            "type": "text",
                            "reason": "Text channel already exists"
                        })
                    else:
                        try:
                            new_tc = await guild.create_text_channel(name=clean_ch_name, category=category, reason=audit_reason)
                            channels_created.append(new_tc)
                            await asyncio.sleep(0.3)
                        except Exception as e:
                            errors.append({"target": f"Text channel '{clean_ch_name}' in '{category.name if category else 'None'}'", "error": str(e)})

        return {
            "categories_created": categories_created,
            "categories_reused": categories_reused,
            "channels_created": channels_created,
            "skipped": skipped,
            "errors": errors
        }

    @bot.hybrid_command(name='createmultichannel', description="Create multiple channels across different categories")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def discord_createmultichannel(ctx, *, layout: str):
        """Create multiple channels across different categories at once.
        Format: Category1: chan1, chan2, voice:vc1 | Category2: chan3, voice:vc2
        Example: /createmultichannel layout: 💬 Community: general, memes | 🔊 Voice: voice:Lounge, voice:Gaming
        """
        await ctx.defer()
        result = await create_multiple_channels(
            guild=ctx.guild,
            structure=layout,
            reason=f"Created by {ctx.author}"
        )

        embed = discord.Embed(
            title="📁 Bulk Channel Creation Report",
            color=discord.Color.green() if not result["errors"] else discord.Color.gold()
        )

        cats_created_str = ", ".join(f"**{c.name}**" for c in result["categories_created"]) or "None"
        embed.add_field(name="🆕 Categories Created", value=cats_created_str, inline=False)

        if result["categories_reused"]:
            cats_reused_str = ", ".join(f"**{c.name}**" for c in result["categories_reused"])
            embed.add_field(name="♻️ Categories Reused", value=cats_reused_str, inline=False)

        if result["channels_created"]:
            ch_list = [f"{'🔊' if isinstance(ch, discord.VoiceChannel) else '💬'} {ch.mention}" for ch in result["channels_created"][:20]]
            ch_text = ", ".join(ch_list)
            if len(result["channels_created"]) > 20:
                ch_text += f" ...and {len(result['channels_created']) - 20} more"
            embed.add_field(name=f"✅ Channels Created ({len(result['channels_created'])})", value=ch_text, inline=False)
        else:
            embed.add_field(name="Channels Created", value="None", inline=False)

        if result["skipped"]:
            skip_list = [f"• `{s['channel']}` ({s['category']}): {s['reason']}" for s in result["skipped"][:10]]
            skip_text = "\n".join(skip_list)
            if len(result["skipped"]) > 10:
                skip_text += f"\n...and {len(result['skipped']) - 10} more"
            embed.add_field(name=f"⚠️ Skipped ({len(result['skipped'])})", value=skip_text, inline=False)

        if result["errors"]:
            err_list = [f"• {e['target']}: `{e['error']}`" for e in result["errors"][:5]]
            embed.add_field(name="❌ Errors", value="\n".join(err_list), inline=False)

        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @bot.hybrid_command(name='createchannel', description="Create a text or voice channel")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def discord_createchannel(ctx, name: str, channel_type: str = "text", category_name: Optional[str] = None):
        """Create a text or voice channel.
        Usage: /createchannel lounge text Community
        """
        category = None
        if category_name:
            category = discord.utils.find(lambda c: c.name.lower() == category_name.lower(), ctx.guild.categories)
            if not category:
                await ctx.send(f"⚠️ Category `{category_name}` not found. Creating channel without category.")

        if channel_type.lower() in ["voice", "vc"]:
            new_channel = await ctx.guild.create_voice_channel(name=name, category=category, reason=f"Created by {ctx.author}")
            channel_icon = "🔊"
        else:
            new_channel = await ctx.guild.create_text_channel(name=name, category=category, reason=f"Created by {ctx.author}")
            channel_icon = "💬"

        embed = discord.Embed(
            title="✅ Channel Created",
            description=f"{channel_icon} Successfully created {new_channel.mention}!",
            color=discord.Color.green()
        )
        if category:
            embed.add_field(name="Category", value=category.name, inline=True)
        embed.add_field(name="Type", value=channel_type.capitalize(), inline=True)
        await ctx.send(embed=embed)

    @bot.hybrid_command(name='deletechannel', description="Delete a channel (defaults to current channel)")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def discord_deletechannel(ctx, channel: Optional[discord.TextChannel] = None):
        """Delete a channel. Defaults to current channel if none specified.
        Usage: /deletechannel #spam
        """
        target_channel = channel or ctx.channel
        channel_name = target_channel.name

        # If deleting the current channel, we won't be able to reply after delete
        is_current = target_channel.id == ctx.channel.id

        await target_channel.delete(reason=f"Deleted by {ctx.author}")

        if not is_current:
            embed = discord.Embed(
                title="🗑️ Channel Deleted",
                description=f"Channel **#{channel_name}** has been deleted.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @bot.hybrid_command(name='createcategory', description="Create a new category for organizing channels")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def discord_createcategory(ctx, *, name: str):
        """Create a new category for organizing channels.
        Usage: /createcategory Gaming
        """
        category = await ctx.guild.create_category(name=name, reason=f"Created by {ctx.author}")
        embed = discord.Embed(
            title="✅ Category Created",
            description=f"📁 Successfully created category **{category.name}**!",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    # ==================== RULES & SERVER SETUP ====================

    @bot.hybrid_command(name='rules', description="Post a sleek community rules embed (Admin only)")
    @commands.has_permissions(administrator=True)
    async def discord_rules(ctx, channel: Optional[discord.TextChannel] = None):
        """Post a professionally formatted community rules embed.
        Usage: /rules or /rules #rules
        """
        target_channel = channel or ctx.channel
        embed = discord.Embed(
            title="📜 Official Server Rules & Guidelines",
            description="Welcome to our server! To ensure an enjoyable and safe environment for everyone, please follow these rules:",
            color=discord.Color.dark_teal()
        )
        embed.add_field(
            name="1️⃣ Be Respectful & Kind",
            value="Treat all members with respect. Harassment, hate speech, bullying, toxicity, and discrimination will not be tolerated.",
            inline=False
        )
        embed.add_field(
            name="2️⃣ No Spam or Advertising",
            value="Avoid spamming messages, emojis, mentions, or images. Self-promotion and server invites are only allowed in designated channels.",
            inline=False
        )
        embed.add_field(
            name="3️⃣ Keep Content Appropriate (SFW)",
            value="No NSFW, explicit, gore, or illegal content. Keep profile pictures, nicknames, and statuses clean.",
            inline=False
        )
        embed.add_field(
            name="4️⃣ Use Channels Appropriately",
            value="Post topics in their respective channels (e.g. memes in #memes, bot commands in #bot-commands).",
            inline=False
        )
        embed.add_field(
            name="5️⃣ Follow Discord's Terms of Service",
            value="All members must adhere to [Discord's Community Guidelines](https://discord.com/guidelines) and [Terms of Service](https://discord.com/terms).",
            inline=False
        )
        embed.add_field(
            name="6️⃣ Respect Staff & Moderation",
            value="Moderators have the final say. If you have an issue, please open a ticket or DM a staff member privately.",
            inline=False
        )
        embed.set_footer(text="By remaining in this server, you agree to follow these rules.")
        await target_channel.send(embed=embed)
        if target_channel != ctx.channel:
            await ctx.send(f"✅ Rules have been posted to {target_channel.mention}!")

    @bot.hybrid_command(name='postrules', description="Post custom rules formatted with pipes (Admin only)")
    @commands.has_permissions(administrator=True)
    async def discord_postrules(ctx, *, content: str):
        """Post custom rules formatted with pipes.
        Usage: /postrules Server Rules | 1. Be kind | 2. No spam | 3. Have fun
        """
        parts = [p.strip() for p in content.split('|')]
        if len(parts) < 2:
            await ctx.send("⚠️ Format: `/postrules Title | Rule 1 | Rule 2 | ...`")
            return

        title = parts[0]
        rules_list = parts[1:]

        embed = discord.Embed(
            title=f"📜 {title}",
            description="Please read and abide by the rules below:",
            color=discord.Color.dark_purple()
        )
        for i, rule in enumerate(rules_list, 1):
            embed.add_field(name=f"Rule {i}", value=rule, inline=False)

        embed.set_footer(text="Thank you for keeping our community safe!")
        await ctx.send(embed=embed)

    @bot.hybrid_command(name='setup_server', description="One-click server setup (Admin only)")
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(administrator=True, manage_channels=True, manage_roles=True)
    async def discord_setup_server(ctx):
        """Automated one-click server setup with categories, channels, roles, and rules."""
        await ctx.defer()
        status_msg = await ctx.send("⚙️ Starting automated server setup... This may take a few seconds.")

        guild = ctx.guild

        # 1. Create Default Roles if they don't exist
        created_roles = []
        role_definitions = [
            ("Admin", discord.Color.red()),
            ("Moderator", discord.Color.blue()),
            ("Member", discord.Color.green())
        ]
        for role_name, role_color in role_definitions:
            existing = discord.utils.get(guild.roles, name=role_name)
            if not existing:
                try:
                    new_r = await guild.create_role(name=role_name, color=role_color, reason="Automated Server Setup")
                    created_roles.append(new_r.name)
                except discord.Forbidden:
                    pass

        # 2. Create Categories & Channels
        structure = [
            {
                "category": "📌 INFORMATION",
                "text": ["welcome-and-rules", "announcements"],
                "voice": []
            },
            {
                "category": "💬 COMMUNITY",
                "text": ["general", "bot-commands", "memes"],
                "voice": []
            },
            {
                "category": "🔊 VOICE CHANNELS",
                "text": [],
                "voice": ["General Voice", "Gaming Lounge"]
            }
        ]

        await create_multiple_channels(guild=guild, structure=structure, reason="Automated Server Setup")
        rules_channel = discord.utils.get(guild.text_channels, name="welcome-and-rules")

        # 3. Post Rules in the rules channel if found
        if rules_channel:
            rules_embed = discord.Embed(
                title="📜 Welcome to the Server!",
                description="Welcome! Please take a moment to review our server rules:",
                color=discord.Color.dark_teal()
            )
            rules_embed.add_field(name="1️⃣ Be Respectful", value="Treat all members with courtesy and kindness.", inline=False)
            rules_embed.add_field(name="2️⃣ No Spam or Self-Promo", value="Keep channels clean and free of unsolicited advertisements.", inline=False)
            rules_embed.add_field(name="3️⃣ SFW Server", value="Keep all conversations, media, and profiles appropriate.", inline=False)
            rules_embed.add_field(name="4️⃣ Follow Discord ToS", value="Adhere to Discord's Terms of Service at all times.", inline=False)
            rules_embed.set_footer(text="Enjoy your stay!")
            await rules_channel.send(embed=rules_embed)

        summary_embed = discord.Embed(
            title="🎉 Server Setup Complete!",
            description="Your server has been customized with essential channels, categories, and roles.",
            color=discord.Color.green()
        )
        summary_embed.add_field(
            name="📁 Categories Created",
            value="• 📌 INFORMATION\n• 💬 COMMUNITY\n• 🔊 VOICE CHANNELS",
            inline=True
        )
        summary_embed.add_field(
            name="🛡️ Roles Created",
            value=", ".join(created_roles) if created_roles else "Existing roles retained",
            inline=True
        )
        summary_embed.add_field(name="📜 Rules Channel", value=rules_channel.mention, inline=False)

        await status_msg.edit(content=None, embed=summary_embed)

    @bot.hybrid_command(name='setwelcome', description="Set the welcome channel for new member greetings (Admin only)")
    @commands.has_permissions(administrator=True)
    async def discord_setwelcome(ctx, channel: Optional[discord.TextChannel] = None):
        """Set the channel where J.A.R.V.I.S. greets new members.
        Usage: /setwelcome #welcome
        """
        target = channel or ctx.channel
        custom_welcome_channels[ctx.guild.id] = target.id
        await ctx.send(f"✅ Welcome channel has been set to {target.mention}!")

    @bot.hybrid_command(name='testwelcome', description="Preview the welcome greeting (Admin only)")
    @commands.has_permissions(administrator=True)
    async def discord_testwelcome(ctx, member: Optional[discord.Member] = None):
        """Preview how the welcome greeting looks.
        Usage: /testwelcome [@member]
        """
        target_member = member or ctx.author
        embed = discord.Embed(
            title=f"👋 Welcome to {ctx.guild.name}!",
            description=(
                f"Greetings, {target_member.mention}! I am **J.A.R.V.I.S.**, the resident AI assistant.\n"
                f"We are delighted to welcome you to our community."
            ),
            color=discord.Color.gold()
        )
        if target_member.display_avatar:
            embed.set_thumbnail(url=target_member.display_avatar.url)

        rules_ch = discord.utils.find(lambda c: "rule" in c.name.lower(), ctx.guild.text_channels)
        if rules_ch:
            embed.add_field(name="📜 Server Rules", value=f"Please review {rules_ch.mention} to get started.", inline=True)

        embed.add_field(name="🤖 AI Assistant", value="Admin-only AI assistant available via `/ask` or mentioning `@Jarvis`.", inline=True)
        embed.add_field(name="👥 Member Count", value=f"You are member **#{ctx.guild.member_count}**", inline=False)
        embed.set_footer(text="J.A.R.V.I.S. Protocol • Welcome System (Preview)")

        await ctx.send(content=f"*(Preview Greeting for {target_member.mention})*", embed=embed)

    def run_discord_bot():
        """Run Discord bot in separate thread"""
        print("🤖 Starting Discord bot...")
        try:
            bot.run(DISCORD_TOKEN)
        except discord.errors.PrivilegedIntentsRequired:
            print("\n" + "=" * 60)
            print("❌ DISCORD ERROR: Privileged Intents Not Enabled!")
            print("=" * 60)
            print("Your bot is configured to use Privileged Gateway Intents (Message Content & Server Members),")
            print("but they have not been enabled in the Discord Developer Portal.")
            print("\nTo fix this:")
            print("  1. Visit: https://discord.com/developers/applications")
            print("  2. Select your bot application -> Click 'Bot' in the left menu")
            print("  3. Scroll down to 'Privileged Gateway Intents'")
            print("  4. Enable:")
            print("     • MESSAGE CONTENT INTENT")
            print("     • SERVER MEMBERS INTENT")
            print("  5. Click 'Save Changes'")
            print("\nAlternatively, set DISCORD_PRIVILEGED_INTENTS=false in your .env to run without them.")
            print("=" * 60 + "\n")
        except discord.errors.LoginFailure:
            print("❌ DISCORD ERROR: Improper or invalid token passed. Check DISCORD_TOKEN in .env.")
        except Exception as e:
            print(f"❌ Discord bot error: {e}")
        print("✅ Discord bot stopped")

# ===== MAIN EXECUTION =====
def main():
    print("=" * 50)
    print("🚀 COMBINED TELEGRAM + DISCORD BOT")
    print("=" * 50)
    
    # Check library installations
    print("\n📋 SETUP STATUS:")
    print(f"Telegram Library: {'✅ Installed' if TELEGRAM_AVAILABLE else '❌ Not installed'}")
    print(f"Discord Library:  {'✅ Installed' if DISCORD_AVAILABLE else '❌ Not installed'}")
    print(f"Google GenAI:     {'✅ Installed' if GENAI_AVAILABLE else '⚠️ Not installed (using HTTP fallback)'}")
    ai_configured = bool(GEMINI_API_KEY) and GEMINI_API_KEY != "your_gemini_api_key_here"
    print(f"AI Assistant:     {'✅ Configured' if ai_configured else '⚠️ Not configured (set GEMINI_API_KEY in .env)'}")
    
    if not TELEGRAM_AVAILABLE and not DISCORD_AVAILABLE:
        print("\n🔧 TO INSTALL MISSING LIBRARIES:")
        print("   pip install -r requirements.txt")
        return

    # Check token readiness
    telegram_ready = TELEGRAM_AVAILABLE and bool(TELEGRAM_TOKEN) and TELEGRAM_TOKEN != "YOUR_TELEGRAM_BOT_TOKEN_HERE"
    discord_ready = DISCORD_AVAILABLE and bool(DISCORD_TOKEN) and DISCORD_TOKEN != "YOUR_DISCORD_BOT_TOKEN_HERE"

    if not telegram_ready:
        print("⚠️  Telegram token is not configured or python-telegram-bot is missing.")
    else:
        print("✅ Telegram token configured.")

    if not discord_ready:
        print("⚠️  DISCORD_TOKEN is not set or still set to placeholder in .env / code.")
        print("   Get it from: https://discord.com/developers/applications")
    else:
        print("✅ Discord token configured.")

    if not telegram_ready and not discord_ready:
        print("\n❌ Neither bot is ready to start. Please configure at least one token.")
        return

    print("\n🔧 STARTING BOTS...")
    if telegram_ready:
        print("   • Telegram bot will respond to /commands in your chat")
    if discord_ready:
        print("   • Discord bot will respond to /commands (Slash) and !commands in your server")
    print("   Press Ctrl+C to stop the bot(s)\n")
    
    # Start configured bots in separate threads
    if telegram_ready:
        telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
        telegram_thread.start()
    
    if discord_ready:
        discord_thread = threading.Thread(target=run_discord_bot, daemon=True)
        discord_thread.start()
    
    try:
        # Keep main thread alive without busy-waiting
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down bots...")
        print("✅ Bots stopped. Goodbye!")

if __name__ == "__main__":
    main()
