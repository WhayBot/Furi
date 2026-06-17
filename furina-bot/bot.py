"""
Furina Bot — Discord Self-Bot with AI Personality
===================================================
A DM-only self-bot that roleplays as Furina de Fontaine (Post-Archon Quest).
Uses Groq API with dual-model strategy for natural, mood-aware conversations.

WARNING: Self-bots violate Discord ToS. Use at your own risk on an alt account.
"""

import discord
from discord.ext import commands, tasks
import asyncio
import sys
import traceback
import random
from datetime import datetime

from config import Config
from database.db_manager import DatabaseManager
from handlers.dm_handler import DMHandler
from utils.ai_client import GroqClient
from utils.proactive_dm import ProactiveDM
from utils.debug_console import DebugConsole


# ==================== Activity Definitions ====================
# Furina's activities that show up as Discord status
# Format: (activity_text, min_duration_minutes, max_duration_minutes)

ACTIVITIES = {
    'morning': [
        ("Reading a novel", 30, 90),
        ("Morning walk with Usher", 20, 40),
        ("Having breakfast (cake ofc)", 15, 30),
        ("Watching the sunrise", 15, 25),
    ],
    'daytime': [
        ("Watching a play at the Opera", 60, 180),
        ("Browsing cake shops", 30, 90),
        ("Reading novels", 45, 120),
        ("Trying new desserts", 30, 60),
        ("Window shopping in Fontaine", 30, 90),
        ("Listening to music", 20, 60),
        ("Writing in diary", 20, 45),
    ],
    'evening': [
        ("Watching theater", 60, 150),
        ("Having afternoon tea & cake", 30, 60),
        ("Listening to music", 30, 90),
        ("Reading before bed", 30, 60),
        ("Watching the stars", 20, 45),
    ],
    'night': [
        ("Late night reading", 45, 120),
        ("Listening to lo-fi", 60, 180),
        ("Can't sleep...", 30, 60),
        ("Stargazing", 20, 40),
    ],
    'sleeping': [
        ("Sleeping... zzz", 120, 300),
        ("Zzz...", 120, 300),
    ],
}


def get_time_period() -> str:
    """Get current time period for activity selection."""
    hour = datetime.now().hour
    if 4 <= hour < 7:
        return 'sleeping'
    elif 7 <= hour < 10:
        return 'morning'
    elif 10 <= hour < 18:
        return 'daytime'
    elif 18 <= hour < 23:
        return 'evening'
    else:
        return 'night'


def get_random_activity() -> tuple:
    """Get a random activity with duration for current time period."""
    period = get_time_period()
    activity_text, min_dur, max_dur = random.choice(ACTIVITIES[period])
    duration = random.randint(min_dur, max_dur)
    return activity_text, duration


# ==================== Bot Class ====================

class FurinaBot(commands.Bot):
    """Main self-bot class for Furina."""

    def __init__(self):
        super().__init__(
            command_prefix="!",       # Won't really be used
            self_bot=True             # Self-bot mode
        )

        # Core components
        self.db = DatabaseManager(Config.DATABASE_PATH)
        self.ai = GroqClient()
        self.dm_handler = None
        self.proactive_dm = None
        self.debug_console = None

        # Activity tracking
        self.current_activity_name = None
        self.next_activity_change = None

        # Debounce: track pending response tasks per user
        # Key: user_id, Value: asyncio.Task
        self._pending_responses: dict = {}
        self._pending_messages: dict = {}
        self.DEBOUNCE_SECONDS = Config.DEBOUNCE_SECONDS

    async def setup_hook(self):
        """Called when bot is starting up."""
        await self.db.initialize()

        self.dm_handler = DMHandler(self.db, self.ai)
        self.proactive_dm = ProactiveDM(self.db, self.ai)

    async def on_ready(self):
        """Called when bot is connected and ready."""
        print("=" * 55)
        print(f"  ✧ Furina Bot Online! ✧")
        print(f"  Logged in as: {self.user.name} ({self.user.id})")
        print(f"  Discord.py-self version: {discord.__version__}")
        print(f"  Mode: DM-only Self-Bot")
        print(f"  AI Models:")
        print(f"    Response: {Config.MODEL_RESPONSE}")
        print(f"    Decision: {Config.MODEL_DECISION}")
        print(f"    Fallback: {Config.MODEL_FALLBACK}")
        print("=" * 55)

        # Set initial activity
        await self.set_new_activity()

        # Start background loops
        if not self.update_activity.is_running():
            self.update_activity.start()
            print("✓ Activity rotation loop started")

        if not self.proactive_dm_loop.is_running():
            self.proactive_dm_loop.start()
            print("✓ Proactive DM loop started")
            
        # Start debug console
        self.debug_console = DebugConsole(self)
        asyncio.create_task(self.debug_console.start())

        print("\n✧ Furina is ready! Waiting for DMs... ✧\n")

    # ==================== Activity System ====================

    async def set_new_activity(self):
        """Set a new random Discord status activity."""
        activity_name, duration_minutes = get_random_activity()

        from datetime import timedelta
        self.current_activity_name = activity_name
        self.next_activity_change = datetime.now() + timedelta(minutes=duration_minutes)

        # Set custom status
        activity = discord.CustomActivity(name=activity_name)
        await self.change_presence(activity=activity)

        hours = duration_minutes // 60
        mins = duration_minutes % 60
        duration_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
        print(f"[ACTIVITY] {activity_name} (for {duration_str})")

    @tasks.loop(minutes=5)
    async def update_activity(self):
        """Check if it's time to change activity."""
        try:
            now = datetime.now()

            if self.next_activity_change and now >= self.next_activity_change:
                await self.set_new_activity()

            # Also change if time period changed
            current_period = get_time_period()
            activity_names = [a[0] for a in ACTIVITIES[current_period]]
            if self.current_activity_name and self.current_activity_name not in activity_names:
                await self.set_new_activity()

        except Exception as e:
            print(f"[ACTIVITY ERROR] {e}")

    @update_activity.before_loop
    async def before_update_activity(self):
        await self.wait_until_ready()

    # ==================== Proactive DM Loop ====================

    @tasks.loop(minutes=Config.PROACTIVE_CHECK_INTERVAL)
    async def proactive_dm_loop(self):
        """Periodically check if Furina should DM someone."""
        try:
            if self.proactive_dm:
                await self.proactive_dm.check_and_send(self)
        except Exception as e:
            print(f"[PROACTIVE ERROR] {e}")
            traceback.print_exc()

    @proactive_dm_loop.before_loop
    async def before_proactive_dm(self):
        await self.wait_until_ready()
        # Wait a bit after startup before first proactive check
        await asyncio.sleep(60)

    # ==================== Message Handler ====================

    async def on_message(self, message: discord.Message):
        """Handle incoming messages — DM only."""
        # Ignore own messages
        if message.author.id == self.user.id:
            return

        # ONLY handle DMs (no guild/server messages)
        if message.guild is not None:
            return

        # Must have content
        if not message.content or not message.content.strip():
            return

        # Debug log
        print(f"[DM] {message.author.name}: {message.content[:60]}{'...' if len(message.content) > 60 else ''}")

        # Debounced handling
        if self.dm_handler:
            # Log immediately (for context)
            await self.dm_handler.log_message_only(message, self.user)

            user_id = str(message.author.id)

            # Clear proactive DM ignore tracking (user is active)
            if self.proactive_dm:
                self.proactive_dm.mark_user_responded(user_id)

            # Cancel any pending response
            if user_id in self._pending_responses:
                self._pending_responses[user_id].cancel()

            # Store latest message
            self._pending_messages[user_id] = message

            # Create delayed response task
            task = asyncio.create_task(
                self._delayed_response(user_id, message)
            )
            self._pending_responses[user_id] = task

    async def _delayed_response(self, user_id: str, message: discord.Message):
        """Wait for debounce period, then process the latest message."""
        try:
            await asyncio.sleep(self.DEBOUNCE_SECONDS)

            # Get latest message (may have been updated)
            latest_message = self._pending_messages.get(user_id, message)

            try:
                # Get mood for typing delay
                user_info = await self.db.get_user_stats(user_id)
                current_mood = user_info.get('current_mood', 'playful') if user_info else 'playful'

                response = await self.dm_handler.handle_message(latest_message, self.user)
                if response:
                    print(f"[REPLY] -> {latest_message.author.name}: {response[:60]}{'...' if len(response) > 60 else ''}")

                    # Send with typing delay
                    dm_channel = latest_message.channel
                    await self.dm_handler.send_with_typing(dm_channel, response, current_mood)
                else:
                    print(f"[SKIP] No response for {latest_message.author.name}")

            except Exception as e:
                print(f"[ERROR] Error handling DM: {e}")
                traceback.print_exc()

        except asyncio.CancelledError:
            # New message arrived — debounce restart
            pass
        finally:
            self._pending_responses.pop(user_id, None)
            self._pending_messages.pop(user_id, None)

    # ==================== Cleanup ====================

    async def close(self):
        """Cleanup on shutdown."""
        print("\n[SHUTDOWN] Furina going offline...")
        await self.db.close()
        await super().close()


# ==================== Main Entry ====================

def main():
    """Main entry point."""
    print("=" * 55)
    print("  ✧ Starting Furina Bot... ✧")
    print("=" * 55)

    # Validate config
    try:
        Config.validate()
        print("✓ Configuration validated")
    except ValueError as e:
        print(f"\n✗ Configuration Error:\n{e}")
        print("\nPlease check your .env file.")
        print("Copy .env.example to .env and fill in your tokens.")
        sys.exit(1)

    # Create and run bot
    bot = FurinaBot()

    try:
        bot.run(Config.DISCORD_TOKEN)
    except discord.LoginFailure:
        print("\n✗ Login failed! Check your DISCORD_TOKEN in .env")
        print("  Make sure you're using a USER token, not a bot token.")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error running bot: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
