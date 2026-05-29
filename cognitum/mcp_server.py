import os
import sys
import json
from mcp.server.fastmcp import FastMCP

# Ensure the project root is in the path so we can import from cognitum
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cognitum.config import settings
from cognitum.core.tools.vault_tool import search_vault as core_search_vault
from cognitum.core.tools.status_tool import get_status as core_get_status
from cognitum.core.profile_store import load_profile as core_load_profile
from cognitum.core.policy_gate import check_action_safety
from cognitum.core.memory_store import store_memory as core_store_memory, search_all_memories as core_search_memories

# Create an MCP server named COGNITUM
mcp = FastMCP("COGNITUM")

@mcp.tool()
def search_obsidian_vault(query: str) -> str:
    """
    Search for a keyword or string inside all Markdown files in the Obsidian Vault.
    Returns a list of matching file paths relative to the vault root.
    """
    matches = core_search_vault(query)
    if not matches:
        return f"No matches found for '{query}' inside the vault."
    return "Matches found in vault:\n" + "\n".join(f"- {m}" for m in matches)

@mcp.tool()
def get_system_status() -> str:
    """
    Retrieve the health metrics, CPU/RAM/Disk stats, and event queue statistics of the COGNITUM host.
    """
    return core_get_status()

@mcp.tool()
def read_user_profile() -> str:
    """
    Read the active user profile details (preferences, goals, active objectives).
    """
    try:
        profile = core_load_profile()
        return json.dumps(profile.model_dump(), indent=2)
    except Exception as e:
        return f"Error loading profile: {e}"

@mcp.tool()
def check_safety_policy(action_type: str, command: str = "", path: str = "") -> str:
    """
    Check if a shell command or file operation complies with the safety policy gate constraints.
    action_type: 'run_command', 'read_file', 'write_file'
    command: The shell command string (for run_command)
    path: The file path (for read_file or write_file)
    """
    params = {}
    if command:
        params["command"] = command
    if path:
        params["path"] = path
    safe, reason = check_action_safety(action_type, params)
    return json.dumps({"safe": safe, "reason": reason}, indent=2)

@mcp.tool()
async def store_cognitive_memory(content: str, memory_type: str = "note.idea") -> str:
    """
    Store a new memory item or study note inside the SQLite event logs.
    """
    try:
        event_id = await core_store_memory(content, memory_type)
        return json.dumps({"success": True, "event_id": event_id})
    except Exception as e:
        return f"Error storing memory: {e}"

@mcp.tool()
async def query_cognitive_memories(query: str) -> str:
    """
    Unified search across both SQLite database log events and Obsidian Vault markdown files for relevant memory context.
    """
    try:
        results = await core_search_memories(query, limit_per_source=5)
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error querying memories: {e}"

if __name__ == "__main__":
    mcp.run()
