import sqlite3
from pathlib import Path
from automations.config import settings

def list_pending_reviews() -> list[dict]:
    """Lists all flashcards currently due for spaced repetition review."""
    db_path = settings.database_path
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM flashcards_state WHERE next_review <= CURRENT_TIMESTAMP ORDER BY next_review ASC"
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()

async def create_review(telegram_chat_id: int) -> int:
    """Saves a review trigger action event in the event queue."""
    from automations.state import save_event
    return await save_event("action.start_review", {"source": "tool_trigger", "chat_id": telegram_chat_id})
