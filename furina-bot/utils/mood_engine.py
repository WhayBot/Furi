"""
Mood Engine — Furina's Emotional State Machine
================================================
Manages per-user mood states with time-based overrides,
decay logic, and sulk-breaker detection.
"""

import random
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from config import Config
from personality.furina_system import FurinaPersonality


class MoodEngine:
    """Manages Furina's mood state per user."""

    VALID_MOODS = ['playful', 'dramatic', 'casual', 'needy', 'sulking', 'vulnerable', 'sleepy']

    def __init__(self):
        # In-memory cache of mood + last update time per user
        self._mood_cache: Dict[str, dict] = {}

    def get_cached_mood(self, user_id: str) -> Optional[str]:
        """Get cached mood for a user."""
        entry = self._mood_cache.get(user_id)
        if entry:
            return entry.get('mood', Config.MOOD_DEFAULT)
        return None

    def update_cache(self, user_id: str, mood: str):
        """Update the in-memory mood cache."""
        self._mood_cache[user_id] = {
            'mood': mood,
            'updated_at': datetime.now(),
        }

    def should_decay(self, user_id: str) -> bool:
        """Check if mood should decay to casual (no interaction for too long)."""
        entry = self._mood_cache.get(user_id)
        if not entry:
            return False

        mood = entry.get('mood', 'playful')
        updated = entry.get('updated_at', datetime.now())
        elapsed = (datetime.now() - updated).total_seconds() / 60  # minutes

        # Sulking doesn't decay — needs explicit trigger
        if mood == 'sulking':
            return False

        # Sleepy decays when time changes
        if mood == 'sleepy':
            time_ctx = FurinaPersonality.get_time_context()
            return time_ctx.get('auto_mood') != 'sleepy'

        # Other moods decay after configured time
        return elapsed > Config.MOOD_DECAY_MINUTES

    def get_time_override(self) -> Optional[str]:
        """Check if current time should force a mood override."""
        time_ctx = FurinaPersonality.get_time_context()
        return time_ctx.get('auto_mood')

    def apply_response_chance(self, mood: str) -> bool:
        """Roll the dice to see if Furina should respond based on mood."""
        mood_cfg = FurinaPersonality.MOOD_CONFIG.get(mood, FurinaPersonality.MOOD_CONFIG['playful'])
        chance = mood_cfg.get('response_chance', 0.85)
        return random.random() < chance

    def check_sulk_override(self, message: str, current_mood: str) -> Optional[str]:
        """
        Check if a message should override sulking mood.
        Returns new mood if override triggered, None otherwise.
        """
        if current_mood != 'sulking':
            return None

        if FurinaPersonality.is_sulk_breaker(message):
            # Gradually come out of sulking
            return random.choice(['casual', 'playful'])

        return None

    def get_response_delay(self, mood: str) -> float:
        """Get a human-like response delay based on mood and time."""
        base_delay = random.uniform(Config.MIN_RESPONSE_DELAY, Config.MAX_RESPONSE_DELAY)
        time_ctx = FurinaPersonality.get_time_context()
        energy = time_ctx.get('energy', 0.8)

        # Mood-based multipliers
        mood_multipliers = {
            'playful': random.uniform(0.8, 1.2),
            'dramatic': random.uniform(0.6, 1.0),     # Quick, excited
            'casual': random.uniform(1.0, 1.5),
            'needy': random.uniform(0.5, 0.9),        # Very quick (wants attention)
            'sulking': random.uniform(2.0, 5.0),      # Slow, reluctant
            'vulnerable': random.uniform(1.2, 2.0),   # Thoughtful
            'sleepy': random.uniform(2.5, 5.0),       # Very slow
        }

        multiplier = mood_multipliers.get(mood, 1.0)

        # Energy inversely affects delay (low energy = slower)
        energy_factor = 1.0 + (1.0 - energy) * 0.5

        delay = base_delay * multiplier * energy_factor

        # Add occasional "thinking" pause
        if random.random() < 0.15:
            delay += random.uniform(0.5, 2.0)

        return min(delay, 8.0)  # Cap at 8 seconds

    def should_show_typing(self, mood: str) -> bool:
        """Decide if typing indicator should be shown."""
        if mood == 'sleepy':
            return random.random() < 0.4
        if mood == 'sulking':
            return random.random() < 0.3
        return random.random() < 0.8
