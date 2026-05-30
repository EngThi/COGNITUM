import json
import os
import asyncio
import httpx
from google import genai
from google.genai import types

from cognitum.config import settings
from cognitum.core.state import save_event, get_unprocessed_events, mark_event_status, get_proxy_mode
from cognitum.core.log import get_logger
from cognitum.core.planner import generate_content_with_backoff, get_genai_client
from cognitum.core.utils import clean_json_text

logger = get_logger("ai_router")

class KimiResponse:
    def __init__(self, text: str):
        self.text = text

async def route_generation(contents, config=None, chat_id=None):
    """Helper that decides whether to route requests through KimiProxy or Gemini Direct."""
    proxy_active = await get_proxy_mode(chat_id)
    if proxy_active:
        logger.info(f"KimiProxy active. Routing classification for chat_id={chat_id}...")
        prompt = ""
        if isinstance(contents, list):
            prompt_parts = []
            for item in contents:
                if isinstance(item, str):
                    prompt_parts.append(item)
                elif hasattr(item, 'text'):
                    prompt_parts.append(item.text)
                else:
                    prompt_parts.append(str(item))
            prompt = "\n".join(prompt_parts)
        elif isinstance(contents, str):
            prompt = contents
        else:
            prompt = str(contents)

        kimi_url_base = os.environ.get("KIMI_PROXY_URL", settings.kimi_proxy_url).rstrip("/")
        url = f"{kimi_url_base}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer your_secret_api_key"
        }
        data = {
            "model": "k2d6",
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        try:
            from cognitum.core.state import record_kimi_use, ensure_kimiproxy_running
            await record_kimi_use()
            await ensure_kimiproxy_running()
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, headers=headers, timeout=120.0)
                response.raise_for_status()
                res_data = response.json()
                content = res_data["choices"][0]["message"]["content"]
                logger.info("Successfully classified content via KimiProxy.")
                return KimiResponse(content)
        except Exception as proxy_err:
            logger.error(f"KimiProxy classification failed: {proxy_err}. Falling back to Gemini Direct...")

    # Fallback to standard generation
    return await generate_content_with_backoff(contents, config)

async def classify_unstructured_input(text: str, chat_id: int | None = None) -> dict:
    prompt = f"""
You are the AI Router of a Personal Cognitive Operating System.
Your job is to classify the unstructured input and return a JSON object.

Unstructured input:
\"\"\"
{text}
\"\"\"

Classify this input into one of these event types:
- `note.idea`: Thoughts, raw ideas, brainstorming.
- `note.mistake`: Mistakes, errors, bugs, or lessons learned.
- `note.session`: Log of a study or active work session.
- `task.created`: To-dos, tasks, or action items.
- `note.concept`: Definitions, computer engineering concepts, academic topics.

Format the response EXACTLY as a JSON object with this structure:
{{
  "type": "one of the types listed above",
  "content": "the cleaned up content (in Markdown format if applicable, keeping all details)",
  "metadata": {{
    "title": "A short, descriptive title",
    "tags": ["relevant", "tags"],
    "context": "extra context extracted if any"
  }}
}}
"""
    response = await generate_content_with_backoff(
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    return json.loads(clean_json_text(response.text))

async def process_router_queue():
    """Fetches all unprocessed events for 'ai_router' and classifies them."""
    events = await get_unprocessed_events("ai_router")
    for event in events:
        event_id = event["id"]
        event_type = event["type"]
        
        if event_type in ["raw.input", "telegram.message"]:
            try:
                payload = json.loads(event["payload"])
                text = payload.get("text", "")
                chat_id = payload.get("chat_id")
                if not text:
                    await mark_event_status(event_id, "ai_router", "processed")
                    continue
                
                logger.info(f"Routing event ID {event_id} of type {event_type}...")
                classification = await classify_unstructured_input(text, chat_id=chat_id)
                
                new_type = classification.get("type", "note.idea")
                new_payload = {
                    "content": classification.get("content", text),
                    "metadata": classification.get("metadata", {}),
                    "original_event_id": event_id,
                    "chat_id": chat_id
                }
                await save_event(new_type, new_payload)
                
                await mark_event_status(event_id, "ai_router", "processed")
                logger.info(f"Event ID {event_id} successfully routed to {new_type}")
            except Exception as e:
                logger.error(f"Failed to route event ID {event_id}: {e}")
                await mark_event_status(event_id, "ai_router", "failed", str(e))
        else:
            await mark_event_status(event_id, "ai_router", "processed")
