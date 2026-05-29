def gemini_to_event(payload: dict) -> dict:
    """Converts a Gemini output structured payload into a CognitiveEvent."""
    return {
        "type": "gemini.output",
        "source": "gemini_model",
        "content": payload.get("text", ""),
        "metadata": payload.get("metadata", {}),
    }
