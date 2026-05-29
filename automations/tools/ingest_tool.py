from automations.state import save_event

async def ingest_event(event_type: str, payload: dict | str) -> int:
    """Ingests a CognitiveEvent into the SQLite event store."""
    return await save_event(event_type, payload)
