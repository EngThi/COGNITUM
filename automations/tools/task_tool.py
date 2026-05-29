from automations.state import save_event

async def create_task_event(text: str, chat_id: int) -> int:
    """Creates a quick task/to-do entry CognitiveEvent."""
    return await save_event("telegram.message", {"text": f"[task] {text}", "source": "tool", "chat_id": chat_id})
