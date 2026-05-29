def telegram_to_event(message: dict) -> dict:
    """Converts a raw Telegram message payload into a standardized CognitiveEvent."""
    return {
        "type": "telegram.message",
        "source": "telegram",
        "content": message.get("text", ""),
        "metadata": {
            "chat_id": message.get("chat_id"),
            "message_id": message.get("message_id"),
        },
    }
