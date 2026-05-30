"""Persistent stdio MCP client sessions for COGNITUM."""

from __future__ import annotations

import asyncio
import json
import shlex
import uuid
from dataclasses import dataclass, field
from typing import Any


_sessions: dict[str, "MCPSession"] = {}
_server_commands: dict[str, str] = {}


@dataclass
class MCPSession:
    server_id: str
    command: str
    process: asyncio.subprocess.Process | None = None
    tools: list[dict[str, Any]] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _initialized: bool = False

    async def start(self) -> None:
        """Start the MCP server process using asyncio stdio pipes."""
        args = shlex.split(self.command)
        if not args:
            raise ValueError(f"Empty MCP command for server {self.server_id}")

        self.process = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    async def _send(self, msg: dict[str, Any]) -> None:
        if self.process is None or self.process.stdin is None:
            raise RuntimeError(f"MCP server {self.server_id} is not running")

        payload = json.dumps(msg, ensure_ascii=False) + "\n"
        self.process.stdin.write(payload.encode("utf-8"))
        await self.process.stdin.drain()

    async def _read_until(self, expected_id: int) -> dict[str, Any]:
        if self.process is None or self.process.stdout is None:
            raise RuntimeError(f"MCP server {self.server_id} is not running")

        async def _read_loop() -> dict[str, Any]:
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    raise RuntimeError(f"MCP server {self.server_id} closed stdout")

                try:
                    msg = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    continue

                if msg.get("id") == expected_id:
                    return msg

        return await asyncio.wait_for(_read_loop(), timeout=30.0)

    async def initialize(self) -> None:
        if self._initialized:
            return

        init_id = uuid.uuid4().int
        await self._send(
            {
                "jsonrpc": "2.0",
                "id": init_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "cognitum", "version": "2.0"},
                },
            }
        )
        init_resp = await self._read_until(init_id)
        if "error" in init_resp:
            raise RuntimeError(f"MCP initialize failed for {self.server_id}: {init_resp['error']}")

        await self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

        list_id = uuid.uuid4().int
        await self._send({"jsonrpc": "2.0", "id": list_id, "method": "tools/list"})
        tools_resp = await self._read_until(list_id)
        if "error" in tools_resp:
            raise RuntimeError(f"MCP tools/list failed for {self.server_id}: {tools_resp['error']}")

        result = tools_resp.get("result") or {}
        self.tools = result.get("tools") or []
        self._initialized = True

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        async with self._lock:
            if not self._initialized:
                await self.initialize()

            call_id = uuid.uuid4().int
            await self._send(
                {
                    "jsonrpc": "2.0",
                    "id": call_id,
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": arguments or {}},
                }
            )
            response = await self._read_until(call_id)

            if "error" in response:
                return f"MCP Tool Error: {json.dumps(response['error'], ensure_ascii=False)}"
            return json.dumps(response.get("result", {}), indent=2, ensure_ascii=False)

    async def stop(self) -> None:
        if self.process is None:
            return

        proc = self.process
        if proc.returncode is None:
            if proc.stdin:
                try:
                    proc.stdin.close()
                    await proc.stdin.wait_closed()
                except Exception:
                    pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()

        self.process = None
        self._initialized = False


def register_server_command(server_id: str, command: str) -> None:
    """Remember a server command so dispatch can restart dead sessions."""
    _server_commands[server_id] = command


async def get_session(server_id: str, command: str) -> MCPSession:
    """Return a live initialized session for an MCP server."""
    register_server_command(server_id, command)
    session = _sessions.get(server_id)
    if session and session.process and session.process.returncode is None:
        return session

    session = MCPSession(server_id=server_id, command=command)
    await session.start()
    await session.initialize()
    _sessions[server_id] = session
    return session


async def get_all_tools() -> list[dict[str, Any]]:
    """Return all tools from active sessions, namespaced as server_id__tool."""
    unified: list[dict[str, Any]] = []
    for server_id, session in list(_sessions.items()):
        if not session.process or session.process.returncode is not None:
            continue
        for tool in session.tools:
            prefixed = dict(tool)
            name = prefixed.get("name")
            if not name:
                continue
            prefixed["name"] = f"{server_id}__{name}"
            unified.append(prefixed)
    return unified


async def dispatch(prefixed_tool_name: str, arguments: dict[str, Any]) -> str:
    """Dispatch a prefixed tool call to the matching MCP session."""
    if "__" not in prefixed_tool_name:
        return "Error: MCP tool name must be prefixed as server_id__tool_name"

    server_id, tool_name = prefixed_tool_name.split("__", 1)
    session = _sessions.get(server_id)
    command = session.command if session else _server_commands.get(server_id)
    if not command:
        return f"Error: MCP server {server_id} is not registered"

    try:
        live_session = await get_session(server_id, command)
        return await live_session.call_tool(tool_name, arguments or {})
    except Exception as exc:
        return f"Error dispatching MCP tool {prefixed_tool_name}: {exc}"


async def shutdown_all() -> None:
    """Stop all active MCP child processes."""
    sessions = list(_sessions.values())
    _sessions.clear()
    await asyncio.gather(*(session.stop() for session in sessions), return_exceptions=True)
