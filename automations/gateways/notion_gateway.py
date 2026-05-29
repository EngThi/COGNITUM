def notion_to_event(payload: dict) -> dict:
    """Converts a Notion webhook database update into a CognitiveEvent."""
    return {
        "type": "notion.update",
        "source": "notion",
        "content": payload.get("page_id", ""),
        "metadata": {
            "database_id": payload.get("database_id"),
            "properties": payload.get("properties", {}),
        },
    }
