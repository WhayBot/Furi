"""
Proactive DM System
====================
Furina sometimes initiates DMs to users she knows.
Makes it feel like chatting with a real friend.
"""

import random
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from config import Config
from personality.furina_system import FurinaPersonality


# Keywords that indicate user is going to sleep / said goodnight
SLEEP_KEYWORDS = [
    'tidur', 'sleep', 'bobo', 'malam', 'night', 'nite',
    'ngantuk', 'sleepy', 'capek', 'cape', 'istirahat', 'rest',
    'duluan', 'off dulu', 'cabut', 'bye', 'dadah', 'selamat malam',
    'good night', 'gn', 'oyasumi', 'nighty',
]


class ProactiveDM:
    """Manages proactive DM initiation logic."""

    def __init__(self, db, ai):
        self.db = db
        self.ai = ai
        # Track daily proactive DM counts per user
        self._daily_counts: dict = {}
        self._last_reset_date: Optional[str] = None
        # Track pending proactive DMs (for ignore detection)
        self._pending_proactive: dict = {}
        # Anti-repetition: track recent proactive messages per user
        self._recent_proactive_msgs: dict = {}
        # Track users who said goodnight (for wake-up DM)
        # Key: user_id, Value: {'sleep_time': datetime, 'wakeup_hour': int}
        self._sleeping_users: dict = {}

    def _reset_daily_counts_if_needed(self):
        """Reset daily counters at midnight."""
        today = datetime.now().strftime('%Y-%m-%d')
        if self._last_reset_date != today:
            self._daily_counts.clear()
            self._last_reset_date = today

    async def check_and_send(self, bot_client):
        """
        Check all users and potentially send proactive DMs.
        Called periodically by the bot's task loop.
        """
        self._reset_daily_counts_if_needed()

        # === QUIET HOURS: No proactive DMs between 11 PM and 8 AM ===
        current_hour = datetime.now().hour
        if current_hour >= 23 or current_hour < 8:
            return


        # Get all users
        users = await self.db.get_all_active_users()
        if not users:
            return

        # === HANDLE WAKE-UP DMs FIRST ===
        for user_id in list(self._sleeping_users.keys()):
            sleep_info = self._sleeping_users[user_id]
            wakeup_hour = sleep_info['wakeup_hour']

            # Time to send wake-up DM?
            if current_hour >= wakeup_hour and current_hour <= wakeup_hour + 2:
                user_info = next((u for u in users if u['user_id'] == user_id), None)
                if user_info:
                    await self._send_wakeup_dm(bot_client, user_info)
                del self._sleeping_users[user_id]

        for user_info in users:
            user_id = user_info['user_id']

            # === CHECK IF PREVIOUS PROACTIVE DM WAS IGNORED ===
            await self._check_ignored_dm(user_info)

            # Check if should DM this user
            should_dm, mood = self._should_proactive_dm(user_info)
            if not should_dm:
                continue

            # Roll the dice
            if random.random() > Config.PROACTIVE_CHANCE:
                continue

            try:
                # === SLEEP CHECK: Don't DM if user said goodnight ===
                if await self._user_said_goodnight(user_id):
                    print(f"[PROACTIVE SKIP] {user_info.get('username', user_id)} said goodnight, not DMing")
                    continue

                # Fetch Discord user
                discord_user = await bot_client.fetch_user(int(user_id))
                if not discord_user:
                    continue

                # Get user notes for personalization
                user_notes = await self.db.get_user_notes_summary(user_id)
                username = user_info.get('display_name') or user_info.get('username', 'User')

                # Build prompt with anti-repetition
                prompt = FurinaPersonality.get_proactive_dm_prompt(
                    mood=mood,
                    username=username,
                    user_notes=user_notes,
                    relationship_level=user_info.get('relationship_level', 0)
                )

                # Inject anti-repetition for proactive messages
                recent = self._recent_proactive_msgs.get(user_id, deque(maxlen=8))
                if len(recent) >= 1:
                    avoid_list = ', '.join([f'"{m[:30]}"' for m in list(recent)[-5:]])
                    prompt += f"\n\n## Anti-Repetisi Proactive DM\nJANGAN pakai kalimat yang mirip dengan ini (sudah pernah dikirim): {avoid_list}\nBuat pesan yang BEDA dan FRESH setiap kali."

                message_content = await self.ai.generate_proactive_message(prompt)
                if not message_content:
                    continue

                # Send the DM
                dm_channel = await discord_user.create_dm()
                await dm_channel.send(message_content)

                # Track for anti-repetition
                if user_id not in self._recent_proactive_msgs:
                    self._recent_proactive_msgs[user_id] = deque(maxlen=8)
                self._recent_proactive_msgs[user_id].append(message_content)

                # Track daily count
                self._daily_counts[user_id] = self._daily_counts.get(user_id, 0) + 1
                await self.db.update_proactive_dm_time(user_id)

                # Mark that we sent a proactive DM (for ignore tracking)
                utc_now = datetime.now(timezone.utc).replace(tzinfo=None)
                self._pending_proactive[user_id] = {
                    'sent_at': utc_now,
                    'ignore_count': self._pending_proactive.get(user_id, {}).get('ignore_count', 0),
                }

                # Log the proactive message
                conversation_id = await self.db.get_or_create_conversation(user_id)
                await self.db.log_message(
                    user_id=user_id,
                    content=message_content,
                    is_bot=True,
                    conversation_id=conversation_id
                )

                print(f"[PROACTIVE DM] Sent to {discord_user.name}: {message_content[:50]}...")

            except Exception as e:
                print(f"[PROACTIVE DM ERROR] User {user_id}: {e}")

    async def _user_said_goodnight(self, user_id: str) -> bool:
        """
        Check if user's last messages indicate they're sleeping.
        If yes, schedule a wake-up DM for the morning.
        """
        # Already marked as sleeping? Skip check
        if user_id in self._sleeping_users:
            return True

        recent = await self.db.get_recent_messages(user_id, limit=5)
        if not recent:
            return False

        user_messages = [m for m in recent if not m.get('is_bot_message', False)]

        for msg in user_messages[-3:]:
            content = msg.get('content', '').lower()
            for keyword in SLEEP_KEYWORDS:
                if keyword in content:
                    created = msg.get('created_at')
                    if created:
                        try:
                            if isinstance(created, str):
                                msg_time = datetime.fromisoformat(created)
                            else:
                                msg_time = created
                            hours_ago = (datetime.now() - msg_time).total_seconds() / 3600
                            if hours_ago <= 8:
                                # Mark as sleeping & schedule wake-up DM
                                wakeup_hour = random.randint(8, 11)
                                self._sleeping_users[user_id] = {
                                    'sleep_time': datetime.now(),
                                    'wakeup_hour': wakeup_hour,
                                }
                                print(f"[SLEEP] {user_id} marked as sleeping. Wake-up DM scheduled ~{wakeup_hour}:00")
                                return True
                        except (ValueError, TypeError):
                            return True
                    else:
                        return True
        return False

    async def _send_wakeup_dm(self, bot_client, user_info: dict):
        """Send a varied 'good morning' DM to a user who was sleeping."""
        user_id = user_info['user_id']
        username = user_info.get('display_name') or user_info.get('username', 'User')

        # Check if user already chatted today — skip wake-up if so
        last_seen_str = user_info.get('last_seen')
        if last_seen_str:
            try:
                if isinstance(last_seen_str, str):
                    last_seen = datetime.fromisoformat(last_seen_str)
                else:
                    last_seen = last_seen_str
                # If user was active less than 2 hours ago, they're already awake
                utc_now = datetime.now(timezone.utc).replace(tzinfo=None)
                hours_since = (utc_now - last_seen).total_seconds() / 3600
                if hours_since < 2.0:
                    print(f"[WAKE-UP SKIP] {username} already active recently, skipping wake-up DM")
                    return
            except (ValueError, TypeError):
                pass

        # Time-appropriate greetings
        current_hour = datetime.now().hour
        if current_hour < 11:
            greetings = [
                f"pagi {username}",
                "udh bangun?",
                "pagi, udh bangun belum",
                f"eh {username} pagi",
                "udh bangun kah",
                "pagii",
            ]
        elif current_hour < 15:
            greetings = [
                f"eh {username}",
                "woi udh siang nih",
                f"{username} udh bangun belum",
                "halo udh siang loh",
                "udh bangun?",
            ]
        else:
            greetings = [
                f"eh {username}",
                "woi kemana aja",
                f"{username} masih hidup?",
                "halo masih tidur apa gimana",
            ]

        # Pick one we haven't used recently
        recent = self._recent_proactive_msgs.get(user_id, deque(maxlen=8))
        available = [m for m in greetings if m not in recent]
        if not available:
            available = greetings

        message = random.choice(available)

        try:
            discord_user = await bot_client.fetch_user(int(user_id))
            if discord_user:
                dm_channel = await discord_user.create_dm()
                await dm_channel.send(message)

                # Track
                if user_id not in self._recent_proactive_msgs:
                    self._recent_proactive_msgs[user_id] = deque(maxlen=8)
                self._recent_proactive_msgs[user_id].append(message)

                self._daily_counts[user_id] = self._daily_counts.get(user_id, 0) + 1
                await self.db.update_proactive_dm_time(user_id)

                conversation_id = await self.db.get_or_create_conversation(user_id)
                await self.db.log_message(user_id=user_id, content=message, is_bot=True, conversation_id=conversation_id)

                print(f"[WAKE-UP DM] Sent to {discord_user.name}: {message}")

        except Exception as e:
            print(f"[WAKE-UP DM ERROR] {user_id}: {e}")

    def _should_proactive_dm(self, user_info: dict) -> tuple:
        """
        Determine if Furina should proactively DM a user.
        Returns: (should_dm: bool, mood_for_dm: str)
        """
        user_id = user_info['user_id']
        relationship = user_info.get('relationship_level', 0)
        current_mood = user_info.get('current_mood', 'playful')
        last_seen_str = user_info.get('last_seen')
        last_proactive_str = user_info.get('last_proactive_dm')

        # Must be at least acquaintance
        if relationship < 1:
            return False, current_mood

        # Check daily limit
        daily_count = self._daily_counts.get(user_id, 0)
        if daily_count >= Config.PROACTIVE_MAX_PER_DAY:
            return False, current_mood

        # Don't DM if currently sulking (she wouldn't initiate)
        if current_mood == 'sulking':
            return False, current_mood

        # Check idle time — user must have been silent for a while
        if last_seen_str:
            try:
                if isinstance(last_seen_str, str):
                    last_seen = datetime.fromisoformat(last_seen_str)
                else:
                    last_seen = last_seen_str

                utc_now = datetime.now(timezone.utc).replace(tzinfo=None)
                idle_hours = (utc_now - last_seen).total_seconds() / 3600

                # If user chatted today (less than 4 hours ago), DON'T proactive DM
                # They already had a conversation — wait until they're truly idle
                if idle_hours < 4.0:
                    return False, current_mood

                # Random threshold between min and max
                threshold = random.uniform(
                    Config.PROACTIVE_MIN_IDLE_HOURS,
                    Config.PROACTIVE_MAX_IDLE_HOURS
                )

                if idle_hours < threshold:
                    return False, current_mood

            except (ValueError, TypeError):
                return False, current_mood
        else:
            return False, current_mood

        # Check cooldown from last proactive DM (min 5 hours between proactive DMs)
        if last_proactive_str:
            try:
                if isinstance(last_proactive_str, str):
                    last_proactive = datetime.fromisoformat(last_proactive_str)
                else:
                    last_proactive = last_proactive_str

                utc_now = datetime.now(timezone.utc).replace(tzinfo=None)
                hours_since_proactive = (utc_now - last_proactive).total_seconds() / 3600
                if hours_since_proactive < 5.0:
                    return False, current_mood
            except (ValueError, TypeError):
                pass

        # Determine mood for the proactive DM
        if current_mood == 'needy':
            dm_mood = 'needy'
        elif relationship >= 2:
            # Close friends get more variety
            dm_mood = random.choice(['playful', 'needy', 'dramatic', 'casual'])
        else:
            dm_mood = random.choice(['playful', 'casual'])

        return True, dm_mood

    # ==================== Ignored DM Detection ====================

    async def _check_ignored_dm(self, user_info: dict):
        """
        Check if a previously sent proactive DM was ignored.
        If ignored: 1st time -> mood=needy, 2nd+ -> mood=sulking.
        """
        user_id = user_info['user_id']

        if user_id not in self._pending_proactive:
            return

        pending = self._pending_proactive[user_id]
        sent_at = pending['sent_at']
        utc_now = datetime.now(timezone.utc).replace(tzinfo=None)
        hours_since = (utc_now - sent_at).total_seconds() / 3600

        # Only check after 2 hours
        if hours_since < 2.0:
            return

        # Check if user sent ANY message since the proactive DM
        last_seen_str = user_info.get('last_seen')
        if last_seen_str:
            try:
                if isinstance(last_seen_str, str):
                    last_seen = datetime.fromisoformat(last_seen_str)
                else:
                    last_seen = last_seen_str

                # User responded after the proactive DM — all good!
                if last_seen > sent_at:
                    print(f"[PROACTIVE] {user_info.get('username', user_id)} responded! Clearing ignore count.")
                    del self._pending_proactive[user_id]
                    return
            except (ValueError, TypeError):
                pass

        # User IGNORED the proactive DM
        ignore_count = pending.get('ignore_count', 0) + 1
        self._pending_proactive[user_id]['ignore_count'] = ignore_count

        current_mood = user_info.get('current_mood', 'playful')
        username = user_info.get('username', user_id)

        if ignore_count == 1 and current_mood != 'needy':
            # First ignore -> needy
            print(f"[MOOD SHIFT] {username} ignored proactive DM -> needy (sad Furi)")
            await self.db.set_user_mood(user_id, 'needy', current_mood, 'proactive_dm_ignored_1')
        elif ignore_count >= 2 and current_mood != 'sulking':
            # Second+ ignore -> sulking
            print(f"[MOOD SHIFT] {username} ignored proactive DM x{ignore_count} -> sulking")
            await self.db.set_user_mood(user_id, 'sulking', current_mood, f'proactive_dm_ignored_{ignore_count}')

        # Clear pending so we don't keep re-triggering
        self._pending_proactive[user_id]['sent_at'] = datetime.now()

    def mark_user_responded(self, user_id: str):
        """Call this when a user sends a message, to clear all tracking."""
        if user_id in self._pending_proactive:
            print(f"[PROACTIVE] User {user_id} responded — clearing ignore tracking.")
            del self._pending_proactive[user_id]
        if user_id in self._sleeping_users:
            print(f"[SLEEP] User {user_id} is awake — clearing sleep status.")
            del self._sleeping_users[user_id]
