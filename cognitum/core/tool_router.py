"""Unified local/MCP tool registry and dispatcher for COGNITUM agents."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import time
from typing import Any, Callable

from cognitum.core import mcp_client


TOOL_SCHEMA_LOCAL: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command (bash) on the host system. Use this to check system configuration, manage git, run scripts, etc.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string", "description": "The exact shell command to execute."}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a text file from the filesystem.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "The absolute path to the file."}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write or overwrite content to a file on the filesystem.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The absolute path to write the file."},
                    "content": {"type": "string", "description": "The full text content to write."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and directories in a given path.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "The directory path to list."}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_vault",
            "description": "Search for a query string across markdown files in Obsidian vault.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "The search term to look for."}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_status",
            "description": "Get the health, queue sizes, and event logs.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "call_composio_action",
            "description": "Execute a Composio integration tool/action through the REST fallback.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action_name": {"type": "string", "description": "The Composio action name."},
                    "parameters": {"type": "object", "description": "Parameters for the action."},
                },
                "required": ["action_name", "parameters"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "call_http_api",
            "description": "Make an HTTP request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {"type": "string", "description": "HTTP method."},
                    "url": {"type": "string", "description": "URL."},
                    "headers": {"type": "object", "description": "Headers.", "default": {}},
                    "json_data": {"type": "object", "description": "JSON payload.", "default": {}},
                },
                "required": ["method", "url"],
            },
        },
    },
]

_DEFAULT_MCP_SERVERS = [
    {"id": "filesystem", "command": "npx -y @modelcontextprotocol/server-filesystem /opt/automation"},
    {"id": "github", "command": "npx -y @modelcontextprotocol/server-github"},
]


def _load_default_servers() -> list[dict[str, str]]:
    raw = os.getenv("MCP_SERVERS_JSON")
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                servers = [
                    {"id": str(item["id"]), "command": str(item["command"])}
                    for item in parsed
                    if isinstance(item, dict) and item.get("id") and item.get("command")
                ]
                if servers:
                    return servers
        except Exception:
            pass
    return list(_DEFAULT_MCP_SERVERS)


MCP_SERVERS_DEFAULT = _load_default_servers()


class ToolRouter:
    def __init__(self, mcp_servers: list[dict[str, str]] | None = None):
        self.mcp_servers = mcp_servers or []
        self._local_names = {tool["function"]["name"] for tool in TOOL_SCHEMA_LOCAL}
        self._failed_until: dict[str, float] = {}
        self._connect_timeout = float(os.getenv("MCP_CONNECT_TIMEOUT", "12"))
        self._retry_after = float(os.getenv("MCP_RETRY_AFTER", "60"))

    async def build_schema(self) -> list[dict[str, Any]]:
        tools = list(TOOL_SCHEMA_LOCAL)

        now = time.monotonic()
        for server in self.mcp_servers:
            server_id = server["id"]
            if self._failed_until.get(server_id, 0) > now:
                continue
            try:
                await asyncio.wait_for(
                    mcp_client.get_session(server_id, server["command"]),
                    timeout=self._connect_timeout,
                )
                self._failed_until.pop(server_id, None)
            except Exception:
                self._failed_until[server_id] = time.monotonic() + self._retry_after
                continue

        try:
            mcp_tools = await mcp_client.get_all_tools()
        except Exception:
            mcp_tools = []

        for tool in mcp_tools:
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.get("name", ""),
                        "description": tool.get("description", "MCP tool"),
                        "parameters": tool.get("inputSchema") or tool.get("parameters") or {"type": "object", "properties": {}},
                    },
                }
            )
        return tools

    async def execute(self, tool_name: str, tool_args: dict[str, Any], local_executor: Callable[..., Any]) -> str:
        if tool_name in self._local_names:
            result = local_executor(tool_name, tool_args or {})
            if inspect.isawaitable(result):
                result = await result
            return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)

        if "__" in tool_name:
            server_id = tool_name.split("__", 1)[0]
            if any(server.get("id") == server_id for server in self.mcp_servers):
                return await mcp_client.dispatch(tool_name, tool_args or {})

        return "Error: unknown tool"


_router = ToolRouter(MCP_SERVERS_DEFAULT)


async def init_tool_router(servers: list[dict[str, str]] | None = None) -> ToolRouter:
    global _router
    _router = ToolRouter(servers or MCP_SERVERS_DEFAULT)
    errors: list[str] = []
    for server in _router.mcp_servers:
        mcp_client.register_server_command(server["id"], server["command"])
        try:
            await asyncio.wait_for(
                mcp_client.get_session(server["id"], server["command"]),
                timeout=_router._connect_timeout,
            )
            _router._failed_until.pop(server["id"], None)
        except Exception as exc:
            _router._failed_until[server["id"]] = time.monotonic() + _router._retry_after
            errors.append(f"{server['id']}: {exc}")
    if errors:
        raise RuntimeError("; ".join(errors))
    return _router


async def build_schema() -> list[dict[str, Any]]:
    return await _router.build_schema()


async def execute(tool_name: str, tool_args: dict[str, Any], local_executor: Callable[..., Any]) -> str:
    return await _router.execute(tool_name, tool_args, local_executor)
