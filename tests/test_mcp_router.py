import asyncio
import json
import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cognitum.core.mcp_client import dispatch, get_session, shutdown_all
from cognitum.core.tool_router import ToolRouter
from cognitum.core.utils import clean_json_text

def _write_fake_mcp_server(tmp_path: Path) -> Path:
    server = tmp_path / "fake_mcp_server.py"
    server.write_text(
        textwrap.dedent(
            r'''
            import json
            import sys

            TOOLS = [
                {
                    "name": "echo",
                    "description": "Echo a message",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"message": {"type": "string"}},
                        "required": ["message"],
                    },
                }
            ]

            for line in sys.stdin:
                msg = json.loads(line)
                method = msg.get("method")
                if method == "initialize":
                    print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": {"protocolVersion": "2024-11-05", "capabilities": {}}}), flush=True)
                elif method == "tools/list":
                    print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": {"tools": TOOLS}}), flush=True)
                elif method == "tools/call":
                    args = msg.get("params", {}).get("arguments", {})
                    print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": {"content": [{"type": "text", "text": args.get("message", "")}]} }), flush=True)
            '''
        ).strip(),
        encoding="utf-8",
    )
    return server

class TestMCPRouter(unittest.TestCase):
    def test_clean_json_text_extracts_fenced_payload(self):
        self.assertEqual(clean_json_text('```json\n{"ok": true}\n```'), '{"ok": true}')
        self.assertEqual(clean_json_text('prefix [1, 2] suffix'), '[1, 2]')

    def test_mcp_session_and_router_dispatch(self):
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            server = _write_fake_mcp_server(tmp_path)
            command = f"{sys.executable} {server}"

            async def run():
                await get_session("fake", command)
                router = ToolRouter([{"id": "fake", "command": command}])
                schema = await router.build_schema()
                self.assertTrue(any(tool["function"]["name"] == "fake__echo" for tool in schema))

                direct_result = await dispatch("fake__echo", {"message": "hello"})
                self.assertIn("hello", direct_result)

                routed_result = await router.execute("fake__echo", {"message": "router"}, lambda name, args: "local")
                self.assertIn("router", routed_result)
                await shutdown_all()

            asyncio.run(run())

if __name__ == "__main__":
    unittest.main()
