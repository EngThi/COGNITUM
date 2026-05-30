import asyncio
import json
import os
from typing import Any

import httpx


COMPOSIO_BASE_URL = "https://backend.composio.dev/api"


def _api_key() -> str | None:
    return os.getenv("COMPOSIO_API_KEY")


async def list_composio_tools() -> list[dict[str, Any]]:
    """List Composio actions as OpenAI-compatible function tool specs."""
    api_key = _api_key()
    if not api_key:
        return []

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{COMPOSIO_BASE_URL}/v1/actions/list/all",
                headers={"x-api-key": api_key},
            )
            resp.raise_for_status()
            data = resp.json()

        actions = data.get("items") or data.get("actions") or data.get("data") or data
        if not isinstance(actions, list):
            return []

        tools: list[dict[str, Any]] = []
        for action in actions:
            if not isinstance(action, dict):
                continue
            name = action.get("name") or action.get("slug") or action.get("action_name")
            if not name:
                continue
            parameters = (
                action.get("parameters")
                or action.get("inputSchema")
                or action.get("input_schema")
                or {"type": "object", "properties": {}}
            )
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": action.get("description") or action.get("displayName") or "Composio action",
                        "parameters": parameters,
                    },
                }
            )
        return tools
    except Exception:
        return []


async def call_composio_action_async(action_name: str, parameters: dict[str, Any]) -> str:
    """Execute a Composio action through the REST API."""
    api_key = _api_key()
    if not api_key:
        return "Error: COMPOSIO_API_KEY not found in environment."

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{COMPOSIO_BASE_URL}/v2/actions/{action_name}/execute",
                headers={"x-api-key": api_key},
                json={"input": parameters or {}, "connectedAccountId": "default"},
            )
            resp.raise_for_status()
            return json.dumps(resp.json(), indent=2, ensure_ascii=False)
    except Exception as exc:
        return f"Error executing Composio action: {exc}"


def call_composio_action(action_name: str, parameters: dict[str, Any]) -> str:
    """Synchronous compatibility wrapper for existing bot.py callers."""
    return asyncio.run(call_composio_action_async(action_name, parameters))
