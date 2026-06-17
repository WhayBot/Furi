"""
Furina Bot Configuration
========================
All settings loaded from environment variables with sensible defaults.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Bot configuration from environment variables."""

    # Discord (User Token for self-bot)
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

    # Groq API
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
    GROQ_API_KEY_BACKUP = os.getenv('GROQ_API_KEY_BACKUP')  # Optional second key from different account

    # AI Models
    MODEL_RESPONSE = "openai/gpt-oss-120b"       # Primary response generator
    MODEL_DECISION = "qwen/qwen3-32b"       # Decision engine (mood, should-respond)
    MODEL_FALLBACK = "llama-3.3-70b-versatile"    # Fallback when primary hits rate limit

    # AI Settings
    MAX_CONTEXT_MESSAGES = 25       # Messages to keep in context per user
    MAX_RESPONSE_LENGTH = 2000     # Discord message character limit

    # Response Timing (human-like delays in seconds)
    MIN_RESPONSE_DELAY = 0.8
    MAX_RESPONSE_DELAY = 2.5
    TYPING_DELAY = 0.3
    DEBOUNCE_SECONDS = 2.5         # Wait for user to finish typing

    # Proactive DM Settings
    PROACTIVE_CHECK_INTERVAL = 30   # Minutes between proactive DM checks
    PROACTIVE_MIN_IDLE_HOURS = 6    # Min hours of user silence before proactive DM
    PROACTIVE_MAX_IDLE_HOURS = 14   # Max hours (random between min and max)
    PROACTIVE_MAX_PER_DAY = 2       # Max proactive DMs per user per day
    PROACTIVE_CHANCE = 0.25         # Probability of sending proactive DM when conditions met

    # Mood Settings
    MOOD_DECAY_MINUTES = 45         # Minutes before mood decays to casual
    MOOD_DEFAULT = 'playful'        # Default mood state

    # Relationship Levels & Dynamic Evaluation
    # Evaluation happens every X interactions based on current level
    REL_EVAL_INTERVALS = {
        0: 10,   # Stranger -> Acquaintance: Check every 10 messages
        1: 25,   # Acquaintance -> Friend: Check every 25 messages
        2: 50,   # Friend -> Close Friend: Check every 50 messages
        3: 100,  # Close Friend -> Special Person: Check every 100 messages
        4: 200,  # Special Person -> Situationship: Check every 200 messages
        5: 300,  # Situationship -> Partner: Check every 300 messages (or direct shoot)
        6: 500,  # Partner: Check every 500 messages (maintenance/breakup check)
    }

    # Relationship Level Constants
    REL_STRANGER = 0
    REL_ACQUAINTANCE = 1
    REL_FRIEND = 2
    REL_CLOSE_FRIEND = 3
    REL_SPECIAL = 4
    REL_SITUATIONSHIP = 5
    REL_PARTNER = 6

    # Database
    DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'database', 'furina.db')

    @classmethod
    def validate(cls):
        """Validate required configuration."""
        errors = []
        if not cls.DISCORD_TOKEN:
            errors.append("DISCORD_TOKEN is not set in .env file")
        if not cls.GROQ_API_KEY:
            errors.append("GROQ_API_KEY is not set in .env file")

        if errors:
            raise ValueError("Configuration errors:\n" + "\n".join(errors))

        return True
