"""
Database Manager for Furina Bot
================================
Async SQLite manager for DM-only self-bot.
Handles users, conversations, messages, notes, and mood persistence.
"""

import aiosqlite
import json
import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional


class DatabaseManager:
    """Async SQLite database manager for Furina Bot."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._connection = None
        self.temp_levels = {}  # {user_id: {"level": int, "expires": datetime}}

    async def initialize(self):
        """Initialize database with schema."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        async with aiosqlite.connect(self.db_path) as db:
            with open(schema_path, 'r') as f:
                await db.executescript(f.read())
            await db.commit()

        print(f"✓ Database initialized at {self.db_path}")

    async def _get_connection(self) -> aiosqlite.Connection:
        """Get database connection."""
        if self._connection is None:
            self._connection = await aiosqlite.connect(self.db_path)
            self._connection.row_factory = aiosqlite.Row
        return self._connection

    async def close(self):
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    # ==================== User Management ====================

    async def get_or_create_user(self, user_id: str, username: str, display_name: str = None) -> Dict:
        """Get or create a user record. Auto-increments interaction count."""
        db = await self._get_connection()

        cursor = await db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        user = await cursor.fetchone()

        if user:
            await db.execute(
                """UPDATE users SET
                   last_seen = CURRENT_TIMESTAMP,
                   interaction_count = interaction_count + 1,
                   username = ?,
                   display_name = ?
                   WHERE user_id = ?""",
                (username, display_name, user_id)
            )
            await db.commit()
            return dict(user)

        # Create new user
        await db.execute(
            """INSERT INTO users (user_id, username, display_name, interaction_count)
               VALUES (?, ?, ?, 1)""",
            (user_id, username, display_name)
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return dict(await cursor.fetchone())

    async def update_relationship_level(self, user_id: str, level: int):
        """Update user relationship level."""
        db = await self._get_connection()
        await db.execute(
            "UPDATE users SET relationship_level = ? WHERE user_id = ?",
            (level, user_id)
        )
        await db.commit()

    async def get_user_stats(self, user_id: str) -> Optional[Dict]:
        """Get user statistics, applying temporary level if active."""
        db = await self._get_connection()
        cursor = await db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
            
        user = dict(row)
        
        # Check and apply temp level
        if user_id in self.temp_levels:
            temp_data = self.temp_levels[user_id]
            if datetime.now() < temp_data['expires']:
                user['relationship_level'] = temp_data['level']
            else:
                del self.temp_levels[user_id]
                
        return user

    async def get_all_active_users(self) -> List[Dict]:
        """Get all users who have interacted (for proactive DM checks)."""
        db = await self._get_connection()
        cursor = await db.execute(
            """SELECT * FROM users
               WHERE interaction_count > 0
               ORDER BY last_seen DESC"""
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_partner(self) -> Optional[Dict]:
        """Get the user who is at the highest relationship level (Partner)."""
        db = await self._get_connection()
        # Ensure we only fetch level 6 (Partner)
        from config import Config
        cursor = await db.execute(
            "SELECT * FROM users WHERE relationship_level = ? LIMIT 1",
            (Config.REL_PARTNER,)
        )
        partner = await cursor.fetchone()
        return dict(partner) if partner else None

    async def update_proactive_dm_time(self, user_id: str):
        """Update the last proactive DM timestamp for a user."""
        db = await self._get_connection()
        await db.execute(
            "UPDATE users SET last_proactive_dm = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()

    # ==================== Mood Management ====================

    async def get_user_mood(self, user_id: str) -> str:
        """Get current mood for a user."""
        db = await self._get_connection()
        cursor = await db.execute(
            "SELECT current_mood FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row['current_mood'] if row else 'playful'

    async def set_user_mood(self, user_id: str, new_mood: str, old_mood: str = None, trigger: str = None):
        """Set mood for a user and log the change."""
        db = await self._get_connection()

        await db.execute(
            "UPDATE users SET current_mood = ? WHERE user_id = ?",
            (new_mood, user_id)
        )

        # Log mood change
        if old_mood and old_mood != new_mood:
            await db.execute(
                """INSERT INTO mood_log (user_id, old_mood, new_mood, trigger_message)
                   VALUES (?, ?, ?, ?)""",
                (user_id, old_mood, new_mood, trigger[:200] if trigger else None)
            )

        await db.commit()

    # ==================== Conversation Management ====================

    async def get_or_create_conversation(self, user_id: str) -> int:
        """Get active conversation or create new one for a DM user."""
        db = await self._get_connection()

        # Look for recent active conversation (within last 30 minutes)
        utc_now = datetime.now(timezone.utc).replace(tzinfo=None)
        cutoff = utc_now - timedelta(minutes=30)
        cursor = await db.execute(
            """SELECT id FROM conversations
               WHERE user_id = ? AND is_active = 1 AND last_activity > ?
               ORDER BY last_activity DESC LIMIT 1""",
            (user_id, cutoff.isoformat())
        )
        conv = await cursor.fetchone()

        if conv:
            await db.execute(
                "UPDATE conversations SET last_activity = CURRENT_TIMESTAMP WHERE id = ?",
                (conv['id'],)
            )
            await db.commit()
            return conv['id']

        # Deactivate old conversations
        await db.execute(
            "UPDATE conversations SET is_active = 0 WHERE user_id = ? AND is_active = 1",
            (user_id,)
        )

        # Create new conversation
        await db.execute(
            "INSERT INTO conversations (user_id) VALUES (?)",
            (user_id,)
        )
        await db.commit()

        cursor = await db.execute("SELECT last_insert_rowid()")
        result = await cursor.fetchone()
        return result[0]

    # ==================== Message Management ====================

    async def log_message(self, user_id: str, content: str,
                          is_bot: bool = False, conversation_id: int = None):
        """Log a message to the database."""
        db = await self._get_connection()
        await db.execute(
            """INSERT INTO messages (conversation_id, user_id, content, is_bot_message)
               VALUES (?, ?, ?, ?)""",
            (conversation_id, user_id, content, is_bot)
        )
        await db.commit()

    async def get_recent_messages(self, user_id: str, limit: int = 25) -> List[Dict]:
        """Get recent messages for a user (chronological order)."""
        db = await self._get_connection()
        cursor = await db.execute(
            """SELECT * FROM messages
               WHERE user_id = ? OR (is_bot_message = 1 AND conversation_id IN (
                   SELECT id FROM conversations WHERE user_id = ?
               ))
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, user_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in reversed(rows)]  # Chronological order

    async def get_conversation_messages(self, conversation_id: int, limit: int = 25) -> List[Dict]:
        """Get messages from a specific conversation."""
        db = await self._get_connection()
        cursor = await db.execute(
            """SELECT * FROM messages
               WHERE conversation_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (conversation_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in reversed(rows)]

    async def clear_user_history(self, user_id: str):
        """Clear all message history for a user."""
        db = await self._get_connection()
        await db.execute(
            "DELETE FROM messages WHERE user_id = ? OR conversation_id IN (SELECT id FROM conversations WHERE user_id = ?)",
            (user_id, user_id)
        )
        await db.execute(
            "UPDATE conversations SET is_active = 0 WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()

    # ==================== User Notes (Long-term Memory) ====================

    async def add_user_note(self, user_id: str, note: str, category: str = "general"):
        """Add a note about a user for long-term memory."""
        db = await self._get_connection()

        # Limit notes per user to prevent bloat
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM user_notes WHERE user_id = ?", (user_id,)
        )
        count = (await cursor.fetchone())['cnt']

        if count >= 25:
            # Remove oldest note
            await db.execute(
                """DELETE FROM user_notes WHERE id = (
                    SELECT id FROM user_notes WHERE user_id = ? ORDER BY created_at ASC LIMIT 1
                )""", (user_id,)
            )

        await db.execute(
            "INSERT INTO user_notes (user_id, note, category) VALUES (?, ?, ?)",
            (user_id, note, category)
        )
        await db.commit()

    async def get_user_notes(self, user_id: str, limit: int = 15) -> List[Dict]:
        """Get notes about a user."""
        db = await self._get_connection()
        cursor = await db.execute(
            """SELECT note, category, created_at FROM user_notes
               WHERE user_id = ? ORDER BY created_at DESC LIMIT ?""",
            (user_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_user_notes_summary(self, user_id: str) -> str:
        """Get a formatted summary of user notes for the AI prompt."""
        notes = await self.get_user_notes(user_id, limit=15)
        if not notes:
            return ""

        summary_parts = []
        for note in notes:
            summary_parts.append(f"- {note['note']}")

        return "\n".join(summary_parts)
