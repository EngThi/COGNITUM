def pipedream_to_event(payload: dict) -> dict:
    """Converts a Pipedream webhook payload into a CognitiveEvent."""
    return {
        "type": "pipedream.webhook",
        "source": "pipedream",
        "content": payload.get("body", ""),
        "metadata": {
            "event_id": payload.get("id"),
            "timestamp": payload.get("timestamp"),
        },
    }
