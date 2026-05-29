# COGNITUM API Documentation

This document describes the request/response payloads, endpoint routing, and schema structures of the COGNITUM Cognition Layer API.

All request/response payloads default to JSON formats.

---

## 1. Profiles Endpoint

### `GET /profile`
Retrieves the active user profile configuration details.

* **Response (200 OK):**
```json
{
  "name": "Thiago",
  "timezone": "America/Sao_Paulo",
  "preferences": {
    "explanations": "Portuguese",
    "verbosity": "medium"
  },
  "objectives": [
    "Upgrade and stabilize COGNITUM layer",
    "Integrate clean cognitive routines in HOMES ecosystem"
  ]
}
```

### `POST /profile`
Updates the profile preferences and saves them to `profiles/default.yaml`.

* **Request Body:** Same schema as Response.
* **Response (200 OK):** Returns the validated updated profile object.

---

## 2. Safety Policies Endpoint

### `GET /policy`
Retrieves the active safety policy constraints (allow/deny lists, restricted hours).

* **Response (200 OK):**
```json
{
  "allowed_commands": ["ls", "git status", "git log"],
  "denied_commands": ["rm -rf /", "rm -rf *", "mkfs"],
  "restricted_hours": {
    "start": "22:30",
    "end": "06:10"
  },
  "safety_gate_enabled": true,
  "allow_sudo": false,
  "enforce_workspace_containment": true
}
```

### `POST /policy/check`
Evaluates whether a command or file access parameter is safe to execute according to active policies.

* **Request Body:**
```json
{
  "action_type": "run_command",
  "parameters": {
    "command": "rm -rf /opt/automation"
  }
}
```
* **Response (200 OK):**
```json
{
  "safe": false,
  "reason": "Action blocked: Command contains forbidden keyword 'rm -rf /'."
}
```

---

## 3. Planning Endpoint

### `POST /plan`
Generates a structured execution plan for achieving the user's objective, factoring in profiles, safety gate rules, and memory context.

* **Request Body:**
```json
{
  "goal": "Backup the COGNITUM database",
  "use_context": true
}
```

* **Response (200 OK):**
```json
{
  "goal": "Backup the COGNITUM database",
  "steps": [
    {
      "step_number": 1,
      "description": "Ensure the backup directory exists under data/backups",
      "tool_recommendation": "mkdir -p data/backups",
      "expected_outcome": "Directory data/backups exists"
    },
    {
      "step_number": 2,
      "description": "Copy the sqlite database file into the backups directory with a timestamp",
      "tool_recommendation": "cp data/cognitum.db data/backups/cognitum_$(date +%F).db",
      "expected_outcome": "Backup file created successfully"
    }
  ],
  "reasoning": "Standard filesystem operations contained within the workspace. Approved by safety gate.",
  "required_contexts": ["data/cognitum.db"]
}
```

---

## 4. Context Endpoint

### `POST /context`
Compiles a consolidated context package containing active profile goals, safety constraints, system resource usage, and query-relevant memories.

* **Request Body:**
```json
{
  "query": "gemini-2.5-flash"
}
```

* **Response (200 OK):**
```json
{
  "profile": {
    "name": "Thiago",
    "timezone": "America/Sao_Paulo",
    "preferences": {"explanations": "Portuguese"},
    "objectives": [...]
  },
  "policy": {
    "safety_gate_enabled": true,
    "restricted_hours": {"start": "22:30", "end": "06:10"},
    ...
  },
  "system_metrics": {
    "cpu_percent": 4.5,
    "ram_percent": 72.8,
    "disk_percent": 18.25
  },
  "memories": [
    {
      "id": 12,
      "source": "database",
      "type": "note.idea",
      "content": "COGNITUM is configured with gemini-2.5-flash model.",
      "created_at": "2026-05-29 19:40:02",
      "metadata": {}
    }
  ],
  "unprocessed_events_count": 0
}
```

---

## 5. Memory Endpoints

### `GET /memory/search`
Queries transaction logs and markdown notes for relevant content.

* **Query Parameters:**
  * `query` (string): Term to search.
  * `limit_per_source` (int, default 5): Results limit.
  * 
* **Response (200 OK):**
```json
{
  "query": "database",
  "results": [
    {
      "id": 14,
      "source": "database",
      "type": "note.idea",
      "content": "Backup the COGNITUM database",
      "created_at": "2026-05-29 19:42:01",
      "metadata": {}
    }
  ]
}
```

### `POST /memory/store`
Stores a new memory directly as an event in the transactional queue.

* **Request Body:**
```json
{
  "content": "Obsidian vault notes are saved under the vault directory",
  "memory_type": "note.idea",
  "metadata": {"tags": ["vault", "notes"]}
}
```

* **Response (200 OK):**
```json
{
  "success": true,
  "event_id": 43
}
```

---

## 6. Legacy Ingestion Compatibility

For backward compatibility with existing automation script calls:

* `GET /health`: Returns disk, ram, cpu, and health state.
* `POST /ideas`: Accepts raw text captures, processing them in background queues.
* `POST /ingest`: Directly ingests standard `CognitiveEvent` payloads.
