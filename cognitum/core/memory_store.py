import os
import json
import sqlite3
import aiosqlite
from pathlib import Path
from pydantic import BaseModel
from typing import List, Dict, Any
from cognitum.config import settings
from cognitum.core.state import save_event

class MemoryResult(BaseModel):
    source: str
    content: str
    metadata: Dict[str, Any]


# We define a plain dict structure for simple, lightweight operation.
# MemoryResult structure:
# {
#   "source": "database" | "vault",
#   "type": str,
#   "content": str,
#   "metadata": dict
# }

async def store_memory(content: str, memory_type: str = "note.idea", metadata: dict = None) -> int:
    """Stores a piece of memory as a cognitive event in the database."""
    payload = {
        "content": content,
        "metadata": metadata or {},
        "timestamp": Path(settings.database_path).stat().st_mtime if Path(settings.database_path).exists() else None
    }
    return await save_event(memory_type, payload)

async def search_database_memories(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Searches SQLite database event payloads for matching substrings."""
    results = []
    if not os.path.exists(settings.database_path):
        return results
        
    try:
        async with aiosqlite.connect(settings.database_path) as db:
            db.row_factory = aiosqlite.Row
            # Search note types or raw inputs matching query
            async with db.execute(
                """
                SELECT id, type, payload, created_at FROM events
                WHERE (type LIKE 'note.%' OR type = 'raw.input' OR type = 'telegram.message')
                ORDER BY id DESC
                """
            ) as cursor:
                rows = await cursor.fetchall()
                for row in rows:
                    try:
                        payload = json.loads(row["payload"])
                        # Check text content in payload
                        text = ""
                        if isinstance(payload, dict):
                            text = payload.get("content", payload.get("text", ""))
                        else:
                            text = str(payload)
                            
                        if query.lower() in text.lower():
                            results.append({
                                "id": row["id"],
                                "source": "database",
                                "type": row["type"],
                                "content": text,
                                "created_at": row["created_at"],
                                "metadata": payload.get("metadata", {}) if isinstance(payload, dict) else {}
                            })
                            if len(results) >= limit:
                                break
                    except Exception:
                        continue
    except Exception:
        pass
    return results

def search_vault_memories(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Searches Markdown files inside the Obsidian Vault for matching substrings."""
    results = []
    vault_path = Path(settings.vault_dir)
    if not vault_path.exists():
        return results
        
    count = 0
    for root, _, files in os.walk(vault_path):
        for file in files:
            if file.endswith(".md"):
                file_path = Path(root) / file
                try:
                    content = file_path.read_text(encoding="utf-8")
                    if query.lower() in content.lower():
                        results.append({
                            "source": "vault",
                            "file_path": str(file_path.relative_to(vault_path)),
                            "content": content[:1000] + ("..." if len(content) > 1000 else ""),
                            "metadata": {
                                "filename": file,
                                "full_path": str(file_path)
                            }
                        })
                        count += 1
                        if count >= limit:
                            return results
                except Exception:
                    pass
    return results

async def search_all_memories(query: str, limit_per_source: int = 5) -> List[Dict[str, Any]]:
    """Combines database event logs and Obsidian Vault markdown results for a unified query representation."""
    db_results = await search_database_memories(query, limit=limit_per_source)
    vault_results = search_vault_memories(query, limit=limit_per_source)
    return db_results + vault_results
