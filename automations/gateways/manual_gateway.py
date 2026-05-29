def manual_to_event(text: str) -> dict:
    """Converts manual stdin CLI input into a CognitiveEvent."""
    return {
        "type": "raw.input",
        "source": "manual_cli",
        "content": text,
        "metadata": {},
    }
