def http_to_event(payload: dict) -> dict:
    """Converts an HTTP JSON payload into a CognitiveEvent."""
    return {
        "type": payload.get("type", "raw.input"),
        "source": payload.get("source", "http_api"),
        "content": payload.get("content", ""),
        "metadata": payload.get("metadata", {}),
    }
