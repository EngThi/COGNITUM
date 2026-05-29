from automations.state import save_event

async def create_flashcard(origin_event_id: int, front: str, back: str) -> int:
    """Creates a flashcard ingestion trigger event."""
    payload = {
        "origin_event_id": origin_event_id,
        "front": front,
        "back": back
    }
    return await save_event("flashcard.created", payload)
