import os
import json
import asyncio
import re
import shutil
import psutil
import aiosqlite
from pathlib import Path
from datetime import datetime, timedelta
from google import genai
from google.genai import types
from google.genai.errors import ClientError

from cognitum.config import settings
from cognitum.core.state import get_unprocessed_events, mark_event_status, save_event
from cognitum.core.log import get_logger
from cognitum.core.planner import generate_content_with_backoff, get_genai_client
from cognitum.core.policy_gate import load_policy, is_in_restricted_hours
from cognitum.core.utils import clean_json_text

logger = get_logger("workers")

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text.strip("_")

async def run_note_worker():
    """Processes note events and writes Markdown files to the vault."""
    events = await get_unprocessed_events("note_worker")
    vault_dir = Path(settings.vault_dir)
    
    for event in events:
        event_id = event["id"]
        event_type = event["type"]
        
        if not event_type.startswith("note."):
            await mark_event_status(event_id, "note_worker", "processed")
            continue
            
        try:
            logger.info(f"[Note Worker] Processing event ID {event_id}...")
            payload = json.loads(event["payload"])
            content = payload.get("content", "")
            metadata = payload.get("metadata", {})
            title = metadata.get("title", "Untitled Note")
            tags = metadata.get("tags", [])
            
            folder_map = {
                "note.idea": "00-inbox",
                "note.concept": "01-concepts",
                "note.session": "02-sessions",
                "note.mistake": "03-mistakes"
            }
            subfolder = folder_map.get(event_type, "00-inbox")
            target_dir = vault_dir / subfolder
            target_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"{timestamp}_{slugify(title)}.md"
            file_path = target_dir / filename
            
            markdown_content = f"""---
title: {title}
date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
type: {event_type}
tags: {json.dumps(tags)}
original_event_id: {event_id}
---

{content}
"""
            file_path.write_text(markdown_content, encoding="utf-8")
            logger.info(f"[Note Worker] Created note file: {file_path}")
            
            await mark_event_status(event_id, "note_worker", "processed")
        except Exception as e:
            logger.error(f"[Note Worker] Error processing event ID {event_id}: {e}")
            await mark_event_status(event_id, "note_worker", "failed", str(e))

async def run_flashcard_worker():
    """Extracts flashcards from new notes using Gemini with backoff, and saves them to vault + DB."""
    events = await get_unprocessed_events("flashcard_worker")
    vault_dir = Path(settings.vault_dir)
    
    for event in events:
        event_id = event["id"]
        event_type = event["type"]
        
        if not event_type.startswith("note."):
            await mark_event_status(event_id, "flashcard_worker", "processed")
            continue
            
        try:
            logger.info(f"[Flashcard Worker] Extracting flashcards from event ID {event_id}...")
            payload = json.loads(event["payload"])
            content = payload.get("content", "")
            metadata = payload.get("metadata", {})
            title = metadata.get("title", "Untitled Note")
            
            prompt = f"""
You are the Flashcard Extraction engine for a Cognitive OS.
Analyze the following note content and extract key flashcards for active recall study.

Note Title: {title}
Note Content:
\"\"\"
{content}
\"\"\"

Create flashcards in Q&A format. Return a JSON array of objects with the structure:
[
  {{
    "front": "Question or prompt?",
    "back": "Answer or explanation."
  }}
]
If there are no facts worth turning into flashcards, return an empty array [].
"""
            response = await generate_content_with_backoff(
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            flashcards = json.loads(clean_json_text(response.text))
            
            if flashcards:
                # 1. Save to Markdown Vault
                flashcards_dir = vault_dir / "04-artifacts" / "flashcards"
                flashcards_dir.mkdir(parents=True, exist_ok=True)
                
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                filename = f"{timestamp}_flashcards_{slugify(title)}.md"
                file_path = flashcards_dir / filename
                
                md_lines = [f"# Flashcards: {title}", f"Origin Note Event ID: {event_id}\n"]
                for i, fc in enumerate(flashcards, 1):
                    md_lines.append(f"### Q{i}: {fc['front']}")
                    md_lines.append(f"**A**: {fc['back']}\n")
                
                file_path.write_text("\n".join(md_lines), encoding="utf-8")
                logger.info(f"[Flashcard Worker] Generated flashcards file: {file_path}")
                
                # 2. Save to SQLite database
                async with aiosqlite.connect(settings.database_path) as db:
                    for idx, fc in enumerate(flashcards):
                        await db.execute(
                            """
                            INSERT OR IGNORE INTO flashcards_state (origin_event_id, card_index, front, back)
                            VALUES (?, ?, ?, ?)
                            """,
                            (event_id, idx, fc["front"], fc["back"])
                        )
                    await db.commit()
                    logger.info(f"[Flashcard Worker] Inserted {len(flashcards)} flashcards into database.")
            
            await mark_event_status(event_id, "flashcard_worker", "processed")
        except Exception as e:
            logger.error(f"[Flashcard Worker] Error extracting flashcards from event ID {event_id}: {e}")
            await mark_event_status(event_id, "flashcard_worker", "failed", str(e))

async def run_daily_brief_worker():
    """Generates today's daily summary brief."""
    events = await get_unprocessed_events("daily_brief_worker")
    vault_dir = Path(settings.vault_dir)
    
    for event in events:
        event_id = event["id"]
        event_type = event["type"]
        
        if event_type != "action.daily_brief":
            await mark_event_status(event_id, "daily_brief_worker", "processed")
            continue
            
        try:
            logger.info(f"[Daily Brief Worker] Generating brief for event ID {event_id}...")
            
            # 1. System Health
            disk = shutil.disk_usage("/")
            memory = psutil.virtual_memory()
            system_health = f"RAM: {memory.percent}% | Disk: {round((disk.used / disk.total) * 100, 2)}% | CPU: {psutil.cpu_percent()}%"
            
            # 2. Queue State
            async with aiosqlite.connect(settings.database_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT COUNT(*) as count FROM events") as cursor:
                    total_events = (await cursor.fetchone())["count"]
                async with db.execute("SELECT COUNT(*) as count FROM processed_events WHERE status = 'failed'") as cursor:
                    failed_events = (await cursor.fetchone())["count"]
                
                # 3. Spaced Repetition Due Cards
                async with db.execute("SELECT COUNT(*) as count FROM flashcards_state WHERE next_review <= CURRENT_TIMESTAMP") as cursor:
                    due_reviews = (await cursor.fetchone())["count"]
            
            # 4. Recent Notes
            recent_notes = []
            for folder in ["00-inbox", "01-concepts", "02-sessions", "03-mistakes"]:
                path = vault_dir / folder
                if path.exists():
                    for f in path.glob("*.md"):
                        mtime = datetime.fromtimestamp(f.stat().st_mtime)
                        if datetime.now() - mtime < timedelta(days=1):
                            recent_notes.append(f"{folder}/{f.name}")
            
            notes_summary = "\n".join([f"- {n}" for n in recent_notes]) if recent_notes else "- No notes captured in the last 24h."
            
            # 5. Format Markdown Brief
            today = datetime.now().strftime("%Y-%m-%d")
            brief_content = f"""# Daily Brief Summary — {today}

## 🖥️ System & Queue Metrics
* **Health:** {system_health}
* **Total Events Logged:** {total_events}
* **Dead-letter / Failed Events:** {failed_events}
* **Flashcards Due for Review:** {due_reviews}

## 📝 Recent Captures (Last 24 Hours)
{notes_summary}

## 🧠 Spaced Repetition Action Required
You have **{due_reviews}** reviews pending. Send `/review` to start a review session.
"""
            # Write to Vault
            briefs_dir = vault_dir / "04-artifacts" / "summaries"
            briefs_dir.mkdir(parents=True, exist_ok=True)
            filename = f"daily_brief_{datetime.now().strftime('%Y%m%d')}.md"
            file_path = briefs_dir / filename
            file_path.write_text(brief_content, encoding="utf-8")
            logger.info(f"[Daily Brief Worker] Created daily brief: {file_path}")
            
            await mark_event_status(event_id, "daily_brief_worker", "processed")
        except Exception as e:
            logger.error(f"[Daily Brief Worker] Error generating brief: {e}")
            await mark_event_status(event_id, "daily_brief_worker", "failed", str(e))

async def run_review_worker():
    """Generates a spaced repetition review session of due flashcards."""
    events = await get_unprocessed_events("review_worker")
    vault_dir = Path(settings.vault_dir)
    
    for event in events:
        event_id = event["id"]
        event_type = event["type"]
        
        if event_type != "action.start_review":
            await mark_event_status(event_id, "review_worker", "processed")
            continue
            
        try:
            logger.info(f"[Review Worker] Creating review session for event ID {event_id}...")
            
            async with aiosqlite.connect(settings.database_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM flashcards_state WHERE next_review <= CURRENT_TIMESTAMP ORDER BY next_review ASC LIMIT 10"
                ) as cursor:
                    due_cards = await cursor.fetchall()
            
            if due_cards:
                session_dir = vault_dir / "06-reviews"
                session_dir.mkdir(parents=True, exist_ok=True)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"review_session_{timestamp}.md"
                file_path = session_dir / filename
                
                md_lines = [
                    f"# Active Recall Review Session — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    "Answer these mentally and track your active compounding memory vault.\n"
                ]
                
                for i, card in enumerate(due_cards, 1):
                    md_lines.append(f"### Card ID {card['id']}: {card['front']}")
                    md_lines.append(f"<!-- Reveal Answer: **A**: {card['back']} -->\n")
                
                file_path.write_text("\n".join(md_lines), encoding="utf-8")
                logger.info(f"[Review Worker] Created review session file: {file_path}")
                
                async with aiosqlite.connect(settings.database_path) as db:
                    for card in due_cards:
                        new_next_review = datetime.now() + timedelta(days=max(1, card["review_count"] * 2))
                        await db.execute(
                            """
                            UPDATE flashcards_state 
                            SET review_count = review_count + 1,
                                next_review = ?,
                                last_reviewed = CURRENT_TIMESTAMP
                            WHERE id = ?
                            """,
                            (new_next_review.strftime("%Y-%m-%d %H:%M:%S"), card["id"])
                        )
                    await db.commit()
            
            await mark_event_status(event_id, "review_worker", "processed")
        except Exception as e:
            logger.error(f"[Review Worker] Error in review generator: {e}")
            await mark_event_status(event_id, "review_worker", "failed", str(e))

async def get_last_kimi_use() -> datetime | None:
    try:
        p = Path(settings.database_path).parent / "last_kimi_use.txt"
        if p.exists():
            content = p.read_text(encoding="utf-8").strip()
            return datetime.fromisoformat(content)
    except Exception:
        pass
    return None

_last_kimiproxy_check = 0.0

async def manage_kimiproxy_service():
    global _last_kimiproxy_check
    import time
    now_time = time.time()
    if now_time - _last_kimiproxy_check < 120.0:
        return
    _last_kimiproxy_check = now_time

    import subprocess
    try:
        res = subprocess.run(
            ["sudo", "systemctl", "is-active", "kimiproxy"],
            capture_output=True,
            text=True
        )
        is_active = (res.stdout.strip() == "active")
        
        should_run = True
        policy = load_policy()
        if is_in_restricted_hours(policy):
            last_use = await get_last_kimi_use()
            if last_use:
                elapsed = (datetime.now() - last_use).total_seconds() / 60.0
                should_run = elapsed < 15.0
            else:
                should_run = False
        else:
            should_run = True
            
        if should_run and not is_active:
            logger.info("[KimiProxy Manager] Starting KimiProxy service...")
            subprocess.run(["sudo", "systemctl", "start", "kimiproxy"], capture_output=True)
        elif not should_run and is_active:
            logger.info("[KimiProxy Manager] Stopping KimiProxy service due to quiet hours inactivity...")
            subprocess.run(["sudo", "systemctl", "stop", "kimiproxy"], capture_output=True)
    except Exception as e:
        logger.error(f"Error in manage_kimiproxy_service: {e}")

from cognitum.core.router import process_router_queue

async def main_loop():
    logger.info("Cognitum background workers started...")
    while True:
        try:
            await manage_kimiproxy_service()
            await process_router_queue()
            await run_note_worker()
            await run_flashcard_worker()
            await run_daily_brief_worker()
            await run_review_worker()
        except Exception as e:
            logger.error(f"Error in workers loop: {e}")
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main_loop())
