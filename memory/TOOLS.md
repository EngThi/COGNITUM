# COGNITUM AGENT TOOLS REFERENCE

This document serves as the primary reference guide for discovering and executing external tools via the Composio platform, Model Context Protocol (MCP), and direct HTTP requests.

---

## 🚀 1. Composio Tools (`call_composio_action`)
Composio manages authentication (OAuth2, API keys) and provides a unified client to run actions across 900+ cloud services.

* **Tool Signature:** `call_composio_action(action_name: str, parameters: dict) -> str`
* **Configuration:** The `COMPOSIO_API_KEY` is pre-configured in the bot's `.env` environment. You do not need to supply it.
* **Target User:** Executions run under the default user space (`user_id="default"`).

### 🔍 How to Discover Actions via Python CLI/Terminal
If you need to find valid action names and parameters, run this Python snippet on the host system using `run_command`:
```bash
# List all active toolkits (apps)
.venv/bin/python -c "from composio import Composio; c = Composio(); print([tk.slug for tk in c.toolkits.list().items])"

# List all available actions for a specific toolkit (e.g., GITHUB or GMAIL)
.venv/bin/python -c "from composio import Composio; c = Composio(); print([(t.slug, t.description) for t in c.tools.get_raw_composio_tools(toolkits=['github'])])"
```

### 📦 Popular Toolkits & Actions Examples
* **GitHub (`github`):**
  * `GITHUB_GET_ABOUT_ME` - Get details of the authenticated GitHub user.
  * `GITHUB_CREATE_ISSUE` - Create a new issue (params: `owner`, `repo`, `title`, `body`).
* **Gmail (`gmail`):**
  * `GMAIL_SEND_EMAIL` - Send an email (params: `userId="me"`, `body` (dict with `recipient`, `subject`, `content`)).
* **Google Calendar (`googlecalendar`):**
  * `GOOGLECALENDAR_CREATE_EVENT` - Create a calendar event.
* **Google Sheets (`googlesheets`):**
  * `GOOGLESHEETS_APPEND_VALUES` - Append rows to a spreadsheet.

---

## 🔌 2. Model Context Protocol (`call_mcp_tool`)
Run tools on stdio-based Model Context Protocol (MCP) servers. The bot automatically manages the server process and RPC handshake.

* **Tool Signature:** `call_mcp_tool(server_command: str, tool_name: str, arguments: dict) -> str`

### 🛠️ Common MCP Servers Available on the VPS
* **Notion Integration:**
  * **Command:** `npx -y @modelcontextprotocol/server-notion`
  * **Description:** Access, edit, search, and manage your Notion workspace.
* **SQLite Database:**
  * **Command:** `npx -y @modelcontextprotocol/server-sqlite`
  * **Description:** Execute raw SQL queries, create tables, or read schema from local database files.
* **HTTP Web Page Fetcher:**
  * **Command:** `npx -y @modelcontextprotocol/server-fetch`
  * **Description:** Cleanly download, parse, and convert any public HTML page into clean Markdown.

---

## 🌐 3. Direct HTTP Client (`call_http_api`)
Make direct, authenticated REST API requests to external web services.

* **Tool Signature:** `call_http_api(method: str, url: str, headers: dict = {}, json_data: dict = {}) -> str`
* **Description:** Use this when a tool is not available in Composio or MCP, allowing you to interface directly with any JSON API.
