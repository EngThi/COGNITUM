import os
from pathlib import Path
from cognitum.config import settings

def search_vault(query: str) -> list[str]:
    """Simple text search inside Markdown files of the Obsidian Vault."""
    vault_path = Path(settings.vault_dir)
    if not vault_path.exists():
        return []
    
    matches = []
    for root, _, files in os.walk(vault_path):
        for file in files:
            if file.endswith(".md"):
                file_path = Path(root) / file
                try:
                    content = file_path.read_text(encoding="utf-8")
                    if query.lower() in content.lower():
                        matches.append(str(file_path.relative_to(vault_path)))
                except Exception:
                    pass
    return matches
