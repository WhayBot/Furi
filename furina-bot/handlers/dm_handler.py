"""
DM Handler — Core DM Message Processing
=========================================
Processes incoming DM messages:
1. Log message to DB
2. Evaluate mood via decision engine
3. Determine if should respond
4. Generate response via primary model
5. Apply typing delay & send
"""

import asyncio
import discord
import random
import re
from typing import Optional, List
from datetime import datetime

from database.db_manager import DatabaseManager
from personality.furina_system import FurinaPersonality
from utils.ai_client import GroqClient
from utils.mood_engine import MoodEngine
from .conversation_tracker import ConversationTracker
from config import Config


class DMHandler:
    """Handles incoming DM messages with mood-aware behavior."""

    def __init__(self, db: DatabaseManager, ai: GroqClient):
        self.db = db
        self.ai = ai
        self.mood_engine = MoodEngine()
        self.conversation_tracker = ConversationTracker()

    async def log_message_only(self, message: discord.Message, bot_user: discord.User):
        """Log a message to DB without generating a response (for debounce)."""
        if message.author.id == bot_user.id:
            return

        user_id = str(message.author.id)
        username = message.author.name
        display_name = message.author.display_name

        # Get or create user
        await self.db.get_or_create_user(user_id, username, display_name)

        # Get or create conversation
        conversation_id = await self.db.get_or_create_conversation(user_id)

        # Log message
        await self.db.log_message(
            user_id=user_id,
            content=message.content,
            is_bot=False,
            conversation_id=conversation_id
        )

        # Update conversation tracker
        self.conversation_tracker.update_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
            message_content=message.content
        )

    async def handle_message(
        self,
        message: discord.Message,
        bot_user: discord.User
    ) -> Optional[str]:
        """
        Process a DM and potentially generate a response.
        Returns response text or None.
        """
        if message.author.id == bot_user.id:
            return None

        user_id = str(message.author.id)
        username = message.author.name
        display_name = message.author.display_name
        content = message.content

        # Get or create user
        user_info = await self.db.get_or_create_user(user_id, username, display_name)

        # Get or create conversation
        conversation_id = await self.db.get_or_create_conversation(user_id)

        # Get conversation state
        conv_state = self.conversation_tracker.get_conversation_state(user_id)

        # Get current mood (from DB, with decay check)
        current_mood = await self._get_effective_mood(user_id, user_info)

        # Check sulk breaker before AI decision
        sulk_override = self.mood_engine.check_sulk_override(content, current_mood)
        if sulk_override:
            print(f"[MOOD] Sulk breaker detected for {username}! {current_mood} -> {sulk_override}")
            current_mood = sulk_override
            await self.db.set_user_mood(user_id, sulk_override, 'sulking', content[:100])
            self.mood_engine.update_cache(user_id, sulk_override)

        # Build recent context for decision engine
        recent_messages = await self.db.get_recent_messages(user_id, limit=5)
        recent_context = ""
        if recent_messages:
            recent_context = "\n".join([
                f"{'Furi' if m.get('is_bot_message') else 'User'}: {m.get('content', '')[:80]}"
                for m in recent_messages[-3:]
            ])

        # Ask decision engine: mood change + should respond?
        decision = await self.ai.analyze_mood_and_respond(
            current_mood=current_mood,
            message_content=content,
            user_info=user_info,
            recent_context=recent_context
        )

        new_mood = decision.get('new_mood', current_mood)
        should_respond = decision.get('should_respond', True)
        reason = decision.get('reason', 'unknown')

        # Update mood if changed
        if new_mood != current_mood:
            print(f"[MOOD] {username}: {current_mood} -> {new_mood} ({reason})")
            await self.db.set_user_mood(user_id, new_mood, current_mood, content[:100])
            self.mood_engine.update_cache(user_id, new_mood)
            current_mood = new_mood

        # Apply mood-based response chance (only for sulking/sleepy)
        if should_respond and current_mood in ('sulking', 'sleepy'):
            should_respond = self.mood_engine.apply_response_chance(current_mood)

        if not should_respond:
            print(f"[SKIP] Not responding to {username} (mood: {current_mood}, reason: {reason})")
            return None

        # Generate response
        response = await self._generate_response(
            user_info=user_info,
            message=message,
            mood=current_mood,
            conversation_id=conversation_id
        )

        if response:
            # Log bot response
            await self.db.log_message(
                user_id=user_id,
                content=response,
                is_bot=True,
                conversation_id=conversation_id
            )

            # Mark bot participation
            self.conversation_tracker.mark_bot_responded(user_id)

            # Update relationship
            await self._update_relationship(user_info, conversation_id)

            # Try to save user notes (long-term memory)
            await self._maybe_save_user_note(user_id, content, display_name or username)

        return response

    async def _get_effective_mood(self, user_id: str, user_info: dict) -> str:
        """Get the effective mood, considering time overrides and decay."""
        # Check time override first
        time_override = self.mood_engine.get_time_override()
        if time_override:
            return time_override

        # Check cache
        cached = self.mood_engine.get_cached_mood(user_id)
        if cached:
            # Check decay
            if self.mood_engine.should_decay(user_id):
                new_mood = 'casual'
                await self.db.set_user_mood(user_id, new_mood, cached, 'mood_decay')
                self.mood_engine.update_cache(user_id, new_mood)
                return new_mood
            return cached

        # Load from DB
        db_mood = await self.db.get_user_mood(user_id)
        self.mood_engine.update_cache(user_id, db_mood)
        return db_mood


    async def _generate_response(
        self,
        user_info: dict,
        message: discord.Message,
        mood: str,
        conversation_id: int
    ) -> Optional[str]:
        """Generate AI response using Furina personality."""
        user_id = str(message.author.id)

        # Get user notes for long-term memory
        user_notes = await self.db.get_user_notes_summary(user_id)

        # Get recent messages for context (across all recent conversations)
        recent_messages = await self.db.get_recent_messages(user_id, limit=Config.MAX_CONTEXT_MESSAGES)

        # Build conversation context
        conversation_context = self.conversation_tracker.build_context_summary(
            user_id, recent_messages
        )

        # Get global partner info (Level 6 user)
        partner_info = await self.db.get_partner()

        # Build enhanced system prompt
        system_prompt = FurinaPersonality.get_enhanced_prompt(
            user_info=user_info,
            mood=mood,
            conversation_context=conversation_context,
            user_notes=user_notes,
            partner_info=partner_info
        )

        # Generate response
        response = await self.ai.generate_response(
            system_prompt=system_prompt,
            messages=recent_messages,
            user_message=message.content
        )

        return response

    async def _maybe_save_user_note(self, user_id: str, message_content: str, username: str):
        """Extract notable info from messages and save as long-term memory."""
        content_lower = message_content.lower()

        note = None
        category = "general"

        # Detect personal info sharing
        personal_indicators = [
            # Indonesian
            ("aku suka ", "preference"), ("gw suka ", "preference"),
            ("aku hobi ", "preference"), ("gw hobi ", "preference"),
            ("favorite aku ", "preference"), ("favorite gw ", "preference"),
            ("kesukaan aku ", "preference"),
            ("aku kerja ", "fact"), ("gw kerja ", "fact"),
            ("aku sekolah ", "fact"), ("gw sekolah ", "fact"),
            ("aku kuliah ", "fact"), ("gw kuliah ", "fact"),
            ("aku tinggal ", "fact"), ("gw tinggal ", "fact"),
            ("aku dari ", "fact"), ("gw dari ", "fact"),
            ("aku lagi ", "topic"), ("gw lagi ", "topic"),
            ("aku main ", "topic"), ("gw main ", "topic"),
            ("nama aku ", "fact"), ("nama gw ", "fact"),
            ("umur aku ", "fact"), ("umur gw ", "fact"),
            # English
            ("i like ", "preference"), ("i love ", "preference"),
            ("my hobby ", "preference"), ("my favorite ", "preference"),
            ("i work ", "fact"), ("i study ", "fact"),
            ("i live in ", "fact"), ("i'm from ", "fact"),
            ("my name is ", "fact"), ("i'm playing ", "topic"),
        ]

        for indicator, cat in personal_indicators:
            if indicator in content_lower:
                idx = content_lower.index(indicator)
                snippet = message_content[idx:idx + 100].strip()
                if len(snippet) > 8:
                    note = f'{username}: "{snippet}"'
                    category = cat
                    break

        if note:
            try:
                await self.db.add_user_note(user_id, note, category)
                print(f"[MEMORY] Saved note about {username}: {note[:60]}...")
            except Exception as e:
                print(f"[MEMORY ERROR] {e}")

    async def _update_relationship(self, user_info: dict, conversation_id: int):
        """Evaluate and update relationship level dynamically using AI."""
        interaction_count = user_info.get('interaction_count', 0)
        current_level = user_info.get('relationship_level', 0)
        username = user_info.get('display_name') or user_info.get('username', 'User')
        user_id = user_info['user_id']

        # Determine if it's time to evaluate
        eval_interval = Config.REL_EVAL_INTERVALS.get(current_level, 500)
        
        # Only evaluate if interaction count aligns with interval (e.g. every 25 msgs)
        if interaction_count > 0 and interaction_count % eval_interval == 0:
            print(f"[RELATIONSHIP] Evaluating {username} (Level {current_level}, {interaction_count} msgs)")
            
            # Check if someone else is already Partner (Level 6)
            partner = await self.db.get_partner()
            is_partner_taken = partner is not None and partner['user_id'] != user_id
            
            # Get recent context for evaluation
            recent_messages = await self.db.get_conversation_messages(conversation_id, limit=20)
            recent_context = "\n".join([
                f"{'Furi' if m.get('is_bot_message') else username}: {m.get('content', '')}"
                for m in recent_messages[-10:]
            ])

            eval_result = await self.ai.evaluate_relationship(
                username=username,
                current_level=current_level,
                interaction_count=interaction_count,
                recent_context=recent_context
            )
            
            new_level = eval_result['new_level']
            reason = eval_result['reason']
            
            # Block Level 6 if taken
            if new_level >= 6 and is_partner_taken:
                print(f"[RELATIONSHIP] {username} tried to reach Level 6, but Furi is taken by {partner['username']}. Capping at Level 5.")
                new_level = 5
                
            if new_level != current_level:
                await self.db.update_relationship_level(user_id, new_level)
                direction = "Upgraded" if new_level > current_level else "Downgraded"
                print(f"[RELATIONSHIP] {direction} {username}: Level {current_level} -> {new_level} (Reason: {reason})")

    def _split_response_naturally(self, response: str) -> List[str]:
        """Split a response into multiple messages at natural break points."""
        sentences = re.split(r'(?<=[.!?])\s+', response)

        if len(sentences) < 2:
            return [response]

        mid = len(sentences) // 2
        part1 = " ".join(sentences[:mid])
        part2 = " ".join(sentences[mid:])

        if len(part1) < 8 or len(part2) < 8:
            return [response]

        return [part1, part2]

    async def send_with_typing(
        self,
        channel: discord.DMChannel,
        response: str,
        mood: str = 'casual'
    ):
        """Send response with realistic typing delay based on mood."""

        # Occasionally split into multiple messages (10% for long responses)
        if len(response) > 50 and random.random() < 0.10:
            parts = self._split_response_naturally(response)
            if len(parts) > 1:
                for i, part in enumerate(parts):
                    if self.mood_engine.should_show_typing(mood):
                        async with channel.typing():
                            delay = len(part) / random.uniform(60, 150)
                            delay = max(0.4, min(delay, 4.0))
                            await asyncio.sleep(delay)
                    else:
                        await asyncio.sleep(random.uniform(0.3, 0.8))

                    await channel.send(part)

                    if i < len(parts) - 1:
                        await asyncio.sleep(random.uniform(0.4, 1.2))
                return

        # Normal single message
        if self.mood_engine.should_show_typing(mood):
            async with channel.typing():
                delay = self.mood_engine.get_response_delay(mood)
                delay += len(response) / random.uniform(80, 200)
                delay = max(0.4, min(delay, 7.0))
                await asyncio.sleep(delay)
        else:
            await asyncio.sleep(self.mood_engine.get_response_delay(mood))

        await channel.send(response)
