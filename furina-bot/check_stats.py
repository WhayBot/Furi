import sqlite3
import os

DB_PATH = os.path.join("database", "furina.db")

def check_levels():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT username, display_name, relationship_level, interaction_count, current_mood, last_seen
        FROM users
        ORDER BY relationship_level DESC, interaction_count DESC
    """)
    users = cursor.fetchall()

    print("=" * 65)
    print(f"{'Username':<20} | {'Level':<5} | {'Interactions':<12} | {'Mood':<10}")
    print("=" * 65)

    for u in users:
        name = u['display_name'] or u['username']
        # Truncate long names
        if len(name) > 19:
            name = name[:16] + "..."
        
        level = u['relationship_level']
        interactions = u['interaction_count']
        mood = u['current_mood']
        
        safe_name = name.encode('ascii', 'ignore').decode('ascii')
        print(f"{safe_name:<20} | {level:<5} | {interactions:<12} | {mood:<10}")

    print("=" * 65)
    conn.close()

if __name__ == "__main__":
    check_levels()
