import asyncio
import sys
import os
from datetime import datetime, timedelta

class DebugConsole:
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.proactive_dm = bot.proactive_dm
        self.history = {}  # Tracks previous state for 'restore' command

    async def start(self):
        """Starts the interactive console loop in the background."""
        loop = asyncio.get_event_loop()
        print("\n[DEBUG CONSOLE] Ready. Type 'help' for commands.")
        
        while True:
            try:
                # Read input from standard input asynchronously without blocking
                line = await loop.run_in_executor(None, sys.stdin.readline)
                
                if not line:
                    break
                
                command = line.strip()
                if not command:
                    continue
                    
                await self.process_command(command)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[DEBUG CONSOLE ERROR] {e}")

    async def _resolve_user(self, username: str) -> dict:
        """Finds user info by checking exact discord username or display name."""
        all_users = await self.db.get_all_active_users()
        for info in all_users:
            if info.get('username', '').lower() == username.lower() or info.get('display_name', '').lower() == username.lower():
                return info
        return None

    async def process_command(self, command: str):
        parts = command.split()
        if not parts:
            return

        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "help":
            print("\n--- DEBUG CONSOLE COMMANDS ---")
            print("level <username> <0-6>   : Ubah relationship level user")
            print("mood <username> <mood>   : Ubah mood user (playful/sulking/dramatic/dll)")
            print("reset_ignore <username>  : Hapus status ignorance (agar Furi bisa Proactive DM lagi)")
            print("stats <username>         : Lihat status user saat ini")
            print("restore <username>       : Kembalikan mood dan level user ke sebelum diubah")
            print("------------------------------\n")

        elif cmd == "level":
            if len(args) < 3:
                print("Usage: level <username> <0-6> <permanent/temp> [hours]")
                return
            
            username = args[0]
            try:
                new_level = int(args[1])
                if not 0 <= new_level <= 6:
                    raise ValueError
            except ValueError:
                print("Level harus berupa angka dari 0 sampai 6.")
                return

            user_info = await self._resolve_user(username)
            if not user_info:
                print(f"User '{username}' tidak ditemukan di database.")
                return

            mode = args[2].lower()
            if mode not in ['permanent', 'temp']:
                print("Mode harus 'permanent' atau 'temp'.")
                return
                
            duration_hours = 1
            if mode == 'temp' and len(args) >= 4:
                try:
                    duration_hours = float(args[3])
                except ValueError:
                    print("Durasi harus berupa angka (jam).")
                    return

            user_id = user_info['user_id']
            current_level = user_info.get('relationship_level', 0)
            
            # Save history
            if user_id not in self.history:
                self.history[user_id] = {'level': current_level, 'mood': user_info.get('current_mood', 'playful')}
            else:
                self.history[user_id]['level'] = current_level

            if mode == 'permanent':
                await self.db.update_relationship_level(user_id, new_level)
                if user_id in self.db.temp_levels:
                    del self.db.temp_levels[user_id]
                print(f"[SUCCESS] Relationship level {username} diubah secara PERMANENT menjadi {new_level}.")
            else:
                expires_at = datetime.now() + timedelta(hours=duration_hours)
                self.db.temp_levels[user_id] = {
                    "level": new_level,
                    "expires": expires_at
                }
                print(f"[SUCCESS] Relationship level {username} diubah secara TEMPORARY menjadi {new_level} selama {duration_hours} jam.")

        elif cmd == "mood":
            if len(args) < 2:
                print("Usage: mood <username> <mood_name>")
                return

            username = args[0]
            new_mood = args[1].lower()

            user_info = await self._resolve_user(username)
            if not user_info:
                print(f"User '{username}' tidak ditemukan di database.")
                return

            user_id = user_info['user_id']
            current_mood = user_info.get('current_mood', 'playful')
            
            # Save history
            if user_id not in self.history:
                self.history[user_id] = {'level': user_info.get('relationship_level', 0), 'mood': current_mood}
            else:
                self.history[user_id]['mood'] = current_mood

            await self.db.set_user_mood(user_id, new_mood, current_mood, "DEBUG CONSOLE FORCE")
            
            # Update mood engine cache
            if hasattr(self.bot, 'dm_handler') and self.bot.dm_handler:
                self.bot.dm_handler.mood_engine.update_cache(user_id, new_mood)
                
            print(f"[SUCCESS] Mood {username} diubah dari {current_mood} menjadi {new_mood}.")

        elif cmd == "reset_ignore":
            if len(args) < 1:
                print("Usage: reset_ignore <username>")
                return
            
            username = args[0]
            user_info = await self._resolve_user(username)
            if not user_info:
                print(f"User '{username}' tidak ditemukan di database.")
                return
                
            user_id = user_info['user_id']
            if self.proactive_dm:
                self.proactive_dm.mark_user_responded(user_id)
                print(f"[SUCCESS] Status ignore/sulking dari proactive DM untuk {username} telah direset.")
            else:
                print("[ERROR] Proactive DM module tidak aktif.")

        elif cmd == "stats":
            if len(args) < 1:
                print("Usage: stats <username>")
                return

            username = args[0]
            user_info = await self._resolve_user(username)
            if not user_info:
                print(f"User '{username}' tidak ditemukan di database.")
                return

            print(f"\n--- STATS FOR {user_info.get('display_name') or user_info.get('username')} ---")
            print(f"Level: {user_info.get('relationship_level', 0)}")
            print(f"Mood : {user_info.get('current_mood', 'playful')}")
            print(f"Chats: {user_info.get('interaction_count', 0)}")
            print("--------------------------\n")

        elif cmd == "restore":
            if len(args) < 1:
                print("Usage: restore <username>")
                return

            username = args[0]
            user_info = await self._resolve_user(username)
            if not user_info:
                print(f"User '{username}' tidak ditemukan di database.")
                return

            user_id = user_info['user_id']
            if user_id not in self.history:
                print(f"[ERROR] Tidak ada history perubahan untuk user '{username}'.")
                return

            old_state = self.history[user_id]
            old_level = old_state['level']
            old_mood = old_state['mood']
            current_mood = user_info.get('current_mood', 'playful')

            # Restore Level
            await self.db.update_relationship_level(user_id, old_level)
            
            # Restore Mood
            await self.db.set_user_mood(user_id, old_mood, current_mood, "DEBUG CONSOLE RESTORE")
            if hasattr(self.bot, 'dm_handler') and self.bot.dm_handler:
                self.bot.dm_handler.mood_engine.update_cache(user_id, old_mood)

            # Clear history after restore
            del self.history[user_id]
            
            print(f"[SUCCESS] {username} direstore ke Level {old_level} dan Mood '{old_mood}'.")

        else:
            print(f"Unknown command: {cmd}. Type 'help' for available commands.")
