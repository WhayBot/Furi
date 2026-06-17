"""
Groq AI Client — Dual-Model Strategy
======================================
- Decision Engine: llama-3.1-8b-instant (mood eval, should-respond)
- Response Generator: gpt-oss-120b (actual Furina responses)
- Fallback: llama-3.3-70b-versatile (when primary hits rate limit)
"""

import asyncio
import re
import json
import random
from groq import Groq
from typing import List, Dict, Optional
from collections import deque
from config import Config


class GroqClient:
    """Async wrapper for Groq API with dual-model and dual-key support."""

    def __init__(self):
        self.api_key = Config.GROQ_API_KEY
        self.api_key_backup = Config.GROQ_API_KEY_BACKUP
        self._client = None
        self._client_backup = None
        self._configured = False
        self._using_backup_key = False

        # Models
        self._response_model = Config.MODEL_RESPONSE
        self._decision_model = Config.MODEL_DECISION
        self._fallback_model = Config.MODEL_FALLBACK
        self._using_fallback = False

        # Anti-repetition tracking
        self._recent_responses: deque = deque(maxlen=15)
        self._recent_starters: deque = deque(maxlen=10)

    def _ensure_configured(self):
        """Ensure API client(s) are initialized."""
        if not self._configured:
            self._client = Groq(api_key=self.api_key)
            if self.api_key_backup:
                self._client_backup = Groq(api_key=self.api_key_backup)
                print("[AI] Backup API key loaded — dual-key rotation enabled")
            self._configured = True

    def _get_active_client(self):
        """Get the currently active Groq client."""
        if self._using_backup_key and self._client_backup:
            return self._client_backup
        return self._client

    def _switch_to_backup_key(self) -> bool:
        """Try switching to backup API key. Returns True if successful."""
        if self._client_backup and not self._using_backup_key:
            self._using_backup_key = True
            print("[AI] Switched to BACKUP API key")
            return True
        elif self._using_backup_key:
            # Already on backup, switch back to primary (maybe primary recovered)
            self._using_backup_key = False
            print("[AI] Switched back to PRIMARY API key")
            return False
        return False

    def _get_generation_params(self) -> dict:
        """Get slightly randomized generation parameters for variety."""
        return {
            'temperature': random.uniform(0.75, 0.95),
            'top_p': random.uniform(0.85, 0.95),
            'max_tokens': random.choice([400, 500, 600, 800]),
        }

    def _get_anti_repetition_instruction(self) -> str:
        """Generate instruction to avoid repetitive openings."""
        if len(self._recent_starters) < 3:
            return ""

        recent_opens = list(self._recent_starters)[-6:]
        avoid_list = ", ".join([f'"{s}"' for s in recent_opens])
        return (
            f"\n\n## Anti-Repetisi\n"
            f"JANGAN mulai response dengan kata-kata ini (sudah dipakai): {avoid_list}. "
            f"Variasikan cara mulai kalimat."
        )

    def _extract_starter(self, text: str) -> str:
        """Extract opening words from a response."""
        words = text.strip().split()[:2]
        return " ".join(words).lower() if words else ""

    def _track_response(self, response: str):
        """Track response for anti-repetition."""
        self._recent_responses.append(response)
        starter = self._extract_starter(response)
        if starter:
            self._recent_starters.append(starter)

    # ==================== Response Generation ====================

    async def generate_response(
        self,
        system_prompt: str,
        messages: List[Dict],
        user_message: str
    ) -> Optional[str]:
        """
        Generate a Furina response using the primary model.
        Falls back to fallback model on rate limit.
        """
        self._ensure_configured()

        # Add anti-repetition
        anti_rep = self._get_anti_repetition_instruction()
        full_system_prompt = system_prompt + anti_rep

        # Build message list
        groq_messages = [
            {"role": "system", "content": full_system_prompt}
        ]

        # Add conversation history
        last_history_user_content = None
        for msg in messages[-Config.MAX_CONTEXT_MESSAGES:]:
            role = "assistant" if msg.get('is_bot_message', False) else "user"
            content = msg.get('content', '')

            # Add timestamp prefix for context
            timestamp = msg.get('created_at', '')
            time_prefix = ""
            if timestamp:
                try:
                    from datetime import datetime
                    if isinstance(timestamp, str):
                        dt = datetime.fromisoformat(timestamp)
                    else:
                        dt = timestamp
                    time_prefix = f"[{dt.strftime('%H:%M')}] "
                except (ValueError, TypeError):
                    pass

            if role == "user":
                last_history_user_content = content
                groq_messages.append({
                    "role": "user",
                    "content": f"{time_prefix}{content}"
                })
            else:
                groq_messages.append({
                    "role": "assistant",
                    "content": content
                })

        # Add current message ONLY if it's not already the last user message in history
        # (This happens because bot.py logs the message to DB BEFORE debounce finishes)
        if user_message and user_message != last_history_user_content:
            groq_messages.append({
                "role": "user",
                "content": user_message
            })

        # Choose model
        model = self._fallback_model if self._using_fallback else self._response_model
        client = self._get_active_client()

        try:
            params = self._get_generation_params()

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model=model,
                    messages=groq_messages,
                    max_tokens=params['max_tokens'],
                    temperature=params['temperature'],
                    top_p=params['top_p'],
                )
            )

            if response.choices and response.choices[0].message.content:
                cleaned = self._clean_response(response.choices[0].message.content)
                if not cleaned:
                    fallback = random.choice(["hm?", "apa", "hmm", "ha?"])
                    self._track_response(fallback)
                    return fallback
                self._track_response(cleaned)

                # Reset fallback flags on success
                if self._using_fallback:
                    self._using_fallback = False
                if self._using_backup_key:
                    self._using_backup_key = False

                return cleaned
            else:
                return "hm?"

        except Exception as e:
            error_msg = str(e)
            print(f"[AI ERROR] {model} (key={'backup' if self._using_backup_key else 'primary'}): {error_msg}")

            is_rate_limit = "rate_limit" in error_msg.lower() or "429" in error_msg
            is_parse_fail = "parsing failed" in error_msg.lower() or "output_parse_failed" in error_msg.lower() or "400" in error_msg
            is_recoverable = is_rate_limit or is_parse_fail or "500" in error_msg or "503" in error_msg

            if is_recoverable:
                if is_rate_limit:
                    # Rate limit: try backup key first (same model)
                    if self._client_backup and not self._using_backup_key:
                        print(f"[AI] Rate limited on primary key, switching to BACKUP key")
                        self._using_backup_key = True
                        return await self.generate_response(system_prompt, messages, user_message)

                # Parse fail or continued rate limit: try fallback model
                if not self._using_fallback:
                    print(f"[AI] Error on {model}, switching to fallback model: {self._fallback_model}")
                    self._using_fallback = True
                    self._using_backup_key = False  # Reset to primary key for fallback model
                    return await self.generate_response(system_prompt, messages, user_message)

                # Fallback model also failed: try backup key + fallback model
                if self._client_backup and not self._using_backup_key:
                    print(f"[AI] Fallback model also failed, trying backup key + fallback model")
                    self._using_backup_key = True
                    return await self.generate_response(system_prompt, messages, user_message)

            # All options exhausted — generic error fallback
            self._using_fallback = False
            self._using_backup_key = False
            return random.choice([
                "bentar ya, lagi loading...",
                "hm? coba lagi",
                "eh bentar",
                "hmm...",
            ])

    # ==================== Decision Engine ====================

    async def analyze_mood_and_respond(
        self,
        current_mood: str,
        message_content: str,
        user_info: dict,
        recent_context: str = ""
    ) -> Dict:
        """
        Use the fast decision engine to:
        1. Evaluate if mood should change
        2. Decide if Furina should respond

        Returns: {'new_mood': str, 'should_respond': bool, 'reason': str}
        """
        self._ensure_configured()

        relationship_level = user_info.get('relationship_level', 0)
        interaction_count = user_info.get('interaction_count', 0)
        username = user_info.get('display_name') or user_info.get('username', 'User')

        # Build relationship context for the analyzer (neutral, no bias)
        if relationship_level == 0:
            rel_context = "Stranger — belum kenal."
        elif relationship_level <= 1:
            rel_context = "Kenalan — baru beberapa kali chat."
        elif relationship_level <= 3:
            rel_context = "Teman — sudah akrab."
        else:
            rel_context = "Sangat dekat — sangat nyaman satu sama lain."

        analysis_prompt = f"""Kamu adalah conversation analyzer untuk karakter "Furi" di DM Discord.

KONTEKS:
- User: {username} (relationship level: {relationship_level}/6, total chat: {interaction_count}x)
- Mood Furi sekarang: {current_mood}
- Pesan user terbaru: "{message_content}"
{f'- Riwayat chat terakhir:\n{recent_context}' if recent_context else '- Ini pesan pertama dari user (belum ada riwayat).'}

TUGAS: Analisis secara NETRAL apakah Furi perlu merespons dan mood apa yang cocok.

PANDUAN RESPOND (netral, tidak bias ke yes/no):
- Analisis ALUR PERCAKAPAN. Apakah pesan user ini membuka/melanjutkan obrolan, atau menutup/mengakhirinya?
- Pertimbangkan: Apakah ada yang PERLU dijawab? Apakah diam justru lebih natural?
- Jika Furi yang MEMULAI chat (proactive DM) dan user cuma balas singkat (misal "pagi juga", "iya", "hm"), Furi TIDAK PERLU langsung nanya lagi — biarkan user yang lanjutin topik kalau mau. Jangan double-greeting.
- Pesan penutup ("oke", "sip", "yaudah", "wkwk", "haha", "makasih") → biasanya tidak perlu dibalas
- Panggilan/Summons ("woi", "p", "ping", nama Furi) → HARUS dijawab (misal: "apa", "kenapa")
- Sapaan baru dari user (user yang memulai, bukan balas sapaan Furi) → respond
- Pertanyaan langsung → respond
- Cerita/curhat/topik baru → respond
- Pesan yang ambigu → gunakan judgement terbaik

PANDUAN MOOD:
- Options: playful, dramatic, casual, needy, sulking, vulnerable, sleepy
- Pilih mood yang PALING COCOK dengan situasi saat ini
- vulnerable → HANYA jika relationship >= 2
- Jangan ganti mood tanpa alasan yang jelas dari konteks chat
- Default ke mood sekarang ({current_mood}) kalau tidak ada alasan kuat untuk berubah

Format jawaban (HANYA 1 baris, tanpa teks lain):
MOOD:mood_baru|RESPOND:yes/no|REASON:alasan_singkat"""

        try:
            client = self._get_active_client()
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model=self._decision_model,
                    messages=[{"role": "user", "content": analysis_prompt}],
                    max_tokens=80,
                    temperature=0.3,
                )
            )

            result_text = response.choices[0].message.content.strip()
            # Clean thinking tags if present
            result_text = re.sub(r'<think>.*?</think>', '', result_text, flags=re.DOTALL).strip()
            if '<think>' in result_text:
                result_text = result_text.split('</think>')[-1].strip()

            return self._parse_decision(result_text, current_mood)

        except Exception as e:
            print(f"[DECISION ERROR] {e}")
            # Default: keep mood, respond
            return {
                'new_mood': current_mood,
                'should_respond': True,
                'reason': 'decision_error_default'
            }

    async def generate_proactive_message(
        self,
        system_prompt: str
    ) -> Optional[str]:
        """Generate a proactive DM message using the response model."""
        self._ensure_configured()

        model = self._fallback_model if self._using_fallback else self._response_model

        try:
            client = self._get_active_client()
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": "Generate a single casual opening DM message. Just the message, nothing else."}
                    ],
                    max_tokens=150,
                    temperature=random.uniform(0.8, 1.0),
                    top_p=0.9,
                )
            )

            if response.choices and response.choices[0].message.content:
                return self._clean_response(response.choices[0].message.content)
            return None

        except Exception as e:
            print(f"[PROACTIVE AI ERROR] {e}")
            return None

    # ==================== Helpers ====================

    def _parse_decision(self, text: str, current_mood: str) -> Dict:
        """Parse the decision engine output."""
        valid_moods = ['playful', 'dramatic', 'casual', 'needy', 'sulking', 'vulnerable', 'sleepy']

        try:
            # Find the line that has the MOOD:...|RESPOND:... format
            for line in text.split('\n'):
                line = line.strip()
                if 'MOOD:' in line and 'RESPOND:' in line:
                    parts = line.split('|')
                    mood_part = [p for p in parts if p.startswith('MOOD:')][0]
                    respond_part = [p for p in parts if p.startswith('RESPOND:')][0]
                    reason_parts = [p for p in parts if p.startswith('REASON:')]

                    new_mood = mood_part.split(':')[1].strip().lower()
                    should_respond = 'yes' in respond_part.split(':')[1].strip().lower()
                    reason = reason_parts[0].split(':')[1].strip() if reason_parts else 'analyzed'

                    if new_mood not in valid_moods:
                        new_mood = current_mood

                    return {
                        'new_mood': new_mood,
                        'should_respond': should_respond,
                        'reason': reason,
                    }
        except (IndexError, ValueError):
            pass

        # Fallback parsing
        return {
            'new_mood': current_mood,
            'should_respond': True,
            'reason': 'parse_fallback',
        }

    async def evaluate_relationship(
        self,
        username: str,
        current_level: int,
        interaction_count: int,
        recent_context: str
    ) -> Dict:
        """
        Evaluate if a user should level up/down in relationship based on chat context.
        Returns: {'new_level': int, 'reason': str}
        """
        self._ensure_configured()

        # Determine what the next level requires
        next_level = min(current_level + 1, 6)
        level_criteria = {
            1: "User sudah beberapa kali chat dan percakapan TIDAK one-sided. Ada timbal balik obrolan.",
            2: "Percakapan sudah meluas ke topik personal (hobi, kesukaan, kehidupan sehari-hari). Ada bercanda dan vibes yang nyambung.",
            3: "User sudah SERING curhat atau sharing hal pribadi. Ada trust dan emotional depth yang jelas. Bukan cuma small talk.",
            4: "Ada tanda-tanda kedekatan LEBIH dari teman — perhatian khusus, kangen, prioritas satu sama lain. Bukan sekadar temen curhat.",
            5: "Ada flirting yang JELAS dan BERULANG dari kedua sisi (user DAN Furi). Gombal, manja, cemburu — kayak pacaran tapi belum resmi.",
            6: "User secara TERANG-TERANGAN NEMBAK/NGAJAK JADIAN (pacaran) dalam chat terbaru, DAN konteksnya romantis/serius. TANPA ajakan jadian yang eksplisit = TETAP LEVEL 5.",
        }
        criteria_text = level_criteria.get(next_level, "Tidak ada kriteria.")

        # Build prompt for evaluation
        eval_prompt = f"""Kamu adalah Relationship Evaluator yang SANGAT KETAT untuk Furina & {username}.
Level saat ini: {current_level}/6
Total Chat: {interaction_count}

0=Stranger, 1=Acquaintance, 2=Friend, 3=Close Friend, 4=Special Person, 5=Situationship/HTS, 6=Partner/Pacar.

CHAT TERBARU MEREKA:
{recent_context}

ATURAN EVALUASI (BACA BAIK-BAIK):
1. Kamu HANYA BOLEH mengubah level MAKSIMAL 1 tingkat naik atau turun. Jawab HANYA {current_level - 1}, {current_level}, atau {next_level}.
2. DEFAULT = TETAP DI LEVEL {current_level}. Jangan naikin level kecuali kriteria JELAS terpenuhi.
3. Naik ke Level {next_level} HANYA JIKA: {criteria_text}
4. Turun ke Level {current_level - 1} HANYA JIKA: {username} sangat toxic, kasar berulang kali, atau ada konflik serius/breakup.
5. Banyak chat BUKAN berarti harus naik level. Yang penting KUALITAS dan KEDALAMAN percakapan.
6. Jika ragu, TETAP di level sekarang.

Jawab dengan format murni JSON:
{{"new_level": [angka], "reason": "[alasan singkat max 10 kata]"}}
"""

        try:
            client = self._get_active_client()
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model=self._decision_model,
                    messages=[{"role": "user", "content": eval_prompt}],
                    max_tokens=150,
                    temperature=0.2,
                )
            )

            result_text = response.choices[0].message.content.strip()
            # Clean thinking tags if present
            result_text = re.sub(r'<think>.*?</think>', '', result_text, flags=re.DOTALL).strip()
            
            # Extract JSON block
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                new_level = int(data.get("new_level", current_level))
                # Bound check: 0-6 range
                new_level = max(0, min(new_level, 6))
                # HARD CLAMP: Only allow +1 or -1 level change per evaluation
                if new_level > current_level + 1:
                    new_level = current_level + 1
                elif new_level < current_level - 1:
                    new_level = current_level - 1
                reason = data.get("reason", "evaluated")
                return {'new_level': new_level, 'reason': reason}
            
            return {'new_level': current_level, 'reason': 'failed_to_parse'}

        except Exception as e:
            print(f"[EVAL ERROR] {e}")
            return {'new_level': current_level, 'reason': 'error'}

    def _clean_response(self, text: str) -> str:
        """Clean up AI response text."""
        text = text.strip()

        # Remove <think>...</think> blocks (Qwen3 / reasoning models)
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        if '<think>' in text:
            text = text.split('<think>')[0].strip()

        # STRIP ALL UNICODE EMOJI — only ASCII emoji allowed
        # This catches standard emoji (😊🎂🍵), emoticons, symbols, flags, etc.
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # Emoticons
            "\U0001F300-\U0001F5FF"  # Misc symbols & pictographs
            "\U0001F680-\U0001F6FF"  # Transport & map
            "\U0001F1E0-\U0001F1FF"  # Flags
            "\U00002702-\U000027B0"  # Dingbats
            "\U000024C2-\U0001F251"  # Enclosed chars
            "\U0001F900-\U0001F9FF"  # Supplemental symbols
            "\U0001FA00-\U0001FA6F"  # Chess symbols
            "\U0001FA70-\U0001FAFF"  # Symbols extended
            "\U00002600-\U000026FF"  # Misc symbols
            "\U0000FE00-\U0000FE0F"  # Variation selectors
            "\U0000200D"             # Zero width joiner
            "\U00002B50"             # Star
            "\U00002764"             # Heart
            "\U0000231A-\U0000231B"  # Watch/hourglass
            "\U000023E9-\U000023F3"  # Various
            "\U000023F8-\U000023FA"  # Various
            "]+",
            flags=re.UNICODE
        )
        text = emoji_pattern.sub('', text)

        # Clean up extra spaces from emoji removal
        text = re.sub(r'  +', ' ', text).strip()

        # Remove wrapping quotes
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]

        # Remove model self-identification prefixes
        for prefix in ['Furi:', 'Furina:', 'Bot:', 'Assistant:', 'Furi :', 'Furina :']:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()

        # Remove markdown artifacts
        text = re.sub(r'^\*\*(.+?)\*\*$', r'\1', text)

        # Ensure Discord message limit
        if len(text) > Config.MAX_RESPONSE_LENGTH:
            text = text[:Config.MAX_RESPONSE_LENGTH - 3] + "..."

        return text
