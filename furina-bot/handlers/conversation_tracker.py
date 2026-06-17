"""
Conversation Tracker — Per-User DM Conversation State
======================================================
Tracks conversation state for each DM user:
topics, message counts, timing, and context building.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class ConversationState:
    """State of an active DM conversation with a user."""
    conversation_id: int
    user_id: str
    started_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    message_count: int = 0
    bot_responded: bool = False


class ConversationTracker:
    """Tracks per-user DM conversation state."""

    def __init__(self):
        self._conversations: Dict[str, ConversationState] = {}
        self._user_contexts: Dict[str, List[str]] = {}
        self.conversation_timeout = timedelta(minutes=30)

    def update_conversation(
        self,
        user_id: str,
        conversation_id: int,
        message_content: str
    ) -> ConversationState:
        """Update conversation state with a new message."""
        now = datetime.now()

        if user_id in self._conversations:
            state = self._conversations[user_id]

            # Check timeout
            if now - state.last_activity > self.conversation_timeout:
                state = ConversationState(
                    conversation_id=conversation_id,
                    user_id=user_id
                )
                self._conversations[user_id] = state
        else:
            state = ConversationState(
                conversation_id=conversation_id,
                user_id=user_id
            )
            self._conversations[user_id] = state

        state.last_activity = now
        state.message_count += 1

        # Track user context
        self._update_user_context(user_id, message_content)

        return state

    def mark_bot_responded(self, user_id: str):
        """Mark that Furina has responded in this conversation."""
        if user_id in self._conversations:
            self._conversations[user_id].bot_responded = True

    def get_conversation_state(self, user_id: str) -> Optional[ConversationState]:
        """Get current conversation state for a user."""
        state = self._conversations.get(user_id)
        if state:
            if datetime.now() - state.last_activity < self.conversation_timeout:
                return state
        return None

    def _update_user_context(self, user_id: str, message: str):
        """Track recent messages for context."""
        if user_id not in self._user_contexts:
            self._user_contexts[user_id] = []

        self._user_contexts[user_id].append(message)
        self._user_contexts[user_id] = self._user_contexts[user_id][-10:]

    def get_user_context(self, user_id: str) -> List[str]:
        """Get recent context for a user."""
        return self._user_contexts.get(user_id, [])

    def build_context_summary(
        self,
        user_id: str,
        recent_messages: List[Dict],
        max_messages: int = 10
    ) -> str:
        """Build a context summary for the AI prompt."""
        state = self.get_conversation_state(user_id)

        parts = []

        if state:
            parts.append(f"Active DM conversation")
            parts.append(f"Messages in this session: {state.message_count}")
            if state.bot_responded:
                parts.append("You have already responded in this conversation")

        if recent_messages:
            parts.append("\nRecent messages:")
            for msg in recent_messages[-max_messages:]:
                content = msg.get('content', '')[:120]
                is_bot = msg.get('is_bot_message', False)

                timestamp = msg.get('created_at', '')
                time_prefix = ""
                if timestamp:
                    try:
                        if isinstance(timestamp, str):
                            dt = datetime.fromisoformat(timestamp)
                        else:
                            dt = timestamp
                        time_prefix = f"[{dt.strftime('%H:%M')}] "
                    except (ValueError, TypeError):
                        pass

                if is_bot:
                    parts.append(f"  {time_prefix}Furi (you): {content}")
                else:
                    parts.append(f"  {time_prefix}User: {content}")

        return "\n".join(parts)

    def clear_conversation(self, user_id: str):
        """Clear conversation state for a user."""
        self._conversations.pop(user_id, None)

    def clear_user_context(self, user_id: str):
        """Clear stored context for a user."""
        self._user_contexts.pop(user_id, None)
