import subprocess
import json

def call_mcp_tool(server_command: str, tool_name: str, arguments: dict) -> str:
    """Executes a tool on an stdio-based Model Context Protocol (MCP) server."""
    try:
        proc = subprocess.Popen(
            server_command,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        def send_msg(msg):
            proc.stdin.write(json.dumps(msg) + "\n")
            proc.stdin.flush()
            
        def read_response(expected_id):
            while True:
                line = proc.stdout.readline()
                if not line:
                    return None
                msg = json.loads(line)
                if msg.get("id") == expected_id:
                    return msg
                    
        # 1. Initialize
        send_msg({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "cognitum-client", "version": "1.0"}
            }
        })
        init_resp = read_response(1)
        if not init_resp:
            proc.terminate()
            return "Error: No initialize response from MCP server."
            
        # 2. Initialized
        send_msg({
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        })
        
        # 3. Call tool
        send_msg({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        })
        tool_resp = read_response(2)
        proc.terminate()
        
        if not tool_resp:
            return "Error: No response from MCP server for tool call."
        if "error" in tool_resp:
            return f"MCP Tool Error: {json.dumps(tool_resp['error'])}"
            
        return json.dumps(tool_resp.get("result", {}), indent=2)
    except Exception as e:
        return f"Exception executing MCP tool: {e}"
