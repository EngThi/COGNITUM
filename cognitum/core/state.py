import sqlite3
import aiosqlite
import json
from pathlib import Path
from cognitum.config import settings

def init_db_sync():
    """Sync initialization for startup if needed, or fallback."""
    db_path = Path(settings.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.touch(exist_ok=True)
    
    conn = sqlite3.connect(settings.database_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_events (
                event_id INTEGER NOT NULL,
                worker_name TEXT NOT NULL,
                status TEXT NOT NULL, -- 'pending', 'processed', 'failed'
                error TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (event_id, worker_name)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS flashcards_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                origin_event_id INTEGER,
                card_index INTEGER,
                front TEXT NOT NULL,
                back TEXT NOT NULL,
                review_count INTEGER DEFAULT 0,
                difficulty REAL DEFAULT 5.0,
                next_review DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_reviewed DATETIME,
                UNIQUE(origin_event_id, card_index)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS telegram_chat_sessions (
                telegram_chat_id INTEGER PRIMARY KEY,
                active_kimi_chat_id TEXT,
                agent_mode INTEGER DEFAULT 0,
                use_proxy INTEGER DEFAULT 1
            )
            """
        )
        try:
            conn.execute("ALTER TABLE telegram_chat_sessions ADD COLUMN agent_mode INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE telegram_chat_sessions ADD COLUMN use_proxy INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS kimi_chat_sessions (
                kimi_chat_id TEXT PRIMARY KEY,
                telegram_chat_id INTEGER NOT NULL,
                title TEXT,
                last_parent_id TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

async def init_db():
    db_path = Path(settings.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.touch(exist_ok=True)
    
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_events (
                event_id INTEGER NOT NULL,
                worker_name TEXT NOT NULL,
                status TEXT NOT NULL,
                error TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (event_id, worker_name)
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS flashcards_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                origin_event_id INTEGER,
                card_index INTEGER,
                front TEXT NOT NULL,
                back TEXT NOT NULL,
                review_count INTEGER DEFAULT 0,
                difficulty REAL DEFAULT 5.0,
                next_review DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_reviewed DATETIME,
                UNIQUE(origin_event_id, card_index)
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS telegram_chat_sessions (
                telegram_chat_id INTEGER PRIMARY KEY,
                active_kimi_chat_id TEXT,
                agent_mode INTEGER DEFAULT 0,
                use_proxy INTEGER DEFAULT 1
            )
            """
        )
        try:
            await db.execute("ALTER TABLE telegram_chat_sessions ADD COLUMN agent_mode INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            await db.execute("ALTER TABLE telegram_chat_sessions ADD COLUMN use_proxy INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS kimi_chat_sessions (
                kimi_chat_id TEXT PRIMARY KEY,
                telegram_chat_id INTEGER NOT NULL,
                title TEXT,
                last_parent_id TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()

async def save_event(event_type: str, payload: dict | str) -> int:
    await init_db()
    payload_str = payload if isinstance(payload, str) else json.dumps(payload)
    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(
            "INSERT INTO events (type, payload) VALUES (?, ?)",
            (event_type, payload_str),
        ) as cursor:
            await db.commit()
            return cursor.lastrowid

async def get_unprocessed_events(worker_name: str):
    await init_db()
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT e.* FROM events e
            LEFT JOIN processed_events p ON e.id = p.event_id AND p.worker_name = ?
            WHERE p.status IS NULL OR p.status != 'processed'
            ORDER BY e.id ASC
            """,
            (worker_name,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def mark_event_status(event_id: int, worker_name: str, status: str, error: str = None):
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            """
            INSERT INTO processed_events (event_id, worker_name, status, error, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(event_id, worker_name) DO UPDATE SET
                status = excluded.status,
                error = excluded.error,
                updated_at = CURRENT_TIMESTAMP
            """,
            (event_id, worker_name, status, error)
        )
        await db.commit()

async def get_active_session(telegram_chat_id: int) -> dict | None:
    await init_db()
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT k.kimi_chat_id, k.last_parent_id, k.title
            FROM telegram_chat_sessions t
            JOIN kimi_chat_sessions k ON t.active_kimi_chat_id = k.kimi_chat_id
            WHERE t.telegram_chat_id = ?
            """,
            (telegram_chat_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def set_active_session(telegram_chat_id: int, kimi_chat_id: str | None):
    await init_db()
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            """
            INSERT INTO telegram_chat_sessions (telegram_chat_id, active_kimi_chat_id)
            VALUES (?, ?)
            ON CONFLICT(telegram_chat_id) DO UPDATE SET active_kimi_chat_id = excluded.active_kimi_chat_id
            """,
            (telegram_chat_id, kimi_chat_id)
        )
        await db.commit()

async def save_kimi_session(kimi_chat_id: str, telegram_chat_id: int, title: str, last_parent_id: str):
    await init_db()
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            """
            INSERT INTO kimi_chat_sessions (kimi_chat_id, telegram_chat_id, title, last_parent_id, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(kimi_chat_id) DO UPDATE SET
                last_parent_id = excluded.last_parent_id,
                updated_at = CURRENT_TIMESTAMP
            """,
            (kimi_chat_id, telegram_chat_id, title, last_parent_id)
        )
        await db.commit()

async def get_user_sessions(telegram_chat_id: int) -> list[dict]:
    await init_db()
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM kimi_chat_sessions WHERE telegram_chat_id = ? ORDER BY updated_at DESC",
            (telegram_chat_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_agent_mode(telegram_chat_id: int) -> bool:
    await init_db()
    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(
            "SELECT agent_mode FROM telegram_chat_sessions WHERE telegram_chat_id = ?",
            (telegram_chat_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return bool(row[0])
            return False

async def toggle_agent_mode(telegram_chat_id: int) -> bool:
    await init_db()
    current = await get_agent_mode(telegram_chat_id)
    new_mode = 0 if current else 1
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            """
            INSERT INTO telegram_chat_sessions (telegram_chat_id, agent_mode)
            VALUES (?, ?)
            ON CONFLICT(telegram_chat_id) DO UPDATE SET agent_mode = excluded.agent_mode
            """,
            (telegram_chat_id, new_mode)
        )
        await db.commit()
    return bool(new_mode)

async def get_proxy_mode(telegram_chat_id: int | None = None) -> bool:
    await init_db()
    async with aiosqlite.connect(settings.database_path) as db:
        if telegram_chat_id is not None:
            async with db.execute(
                "SELECT use_proxy FROM telegram_chat_sessions WHERE telegram_chat_id = ?",
                (telegram_chat_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row is not None:
                    return bool(row[0]) if row[0] is not None else True
                return True
        else:
            async with db.execute(
                "SELECT use_proxy FROM telegram_chat_sessions ORDER BY ROWID DESC LIMIT 1"
            ) as cursor:
                row = await cursor.fetchone()
                if row is not None:
                    return bool(row[0]) if row[0] is not None else True
                return True

async def toggle_proxy_mode(telegram_chat_id: int) -> bool:
    await init_db()
    current = await get_proxy_mode(telegram_chat_id)
    new_mode = 0 if current else 1
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            """
            INSERT INTO telegram_chat_sessions (telegram_chat_id, use_proxy)
            VALUES (?, ?)
            ON CONFLICT(telegram_chat_id) DO UPDATE SET use_proxy = excluded.use_proxy
            """,
            (telegram_chat_id, new_mode)
        )
        await db.commit()
    return bool(new_mode)

async def record_kimi_use():
    from datetime import datetime
    try:
        p = Path(settings.database_path).parent / "last_kimi_use.txt"
        p.write_text(datetime.now().isoformat(), encoding="utf-8")
    except Exception:
        pass

async def ensure_kimiproxy_running():
    import subprocess
    import asyncio
    import os
    kimi_url = os.environ.get("KIMI_PROXY_URL", settings.kimi_proxy_url)
    if "localhost" not in kimi_url and "127.0.0.1" not in kimi_url:
        return
    try:
        res = subprocess.run(
            ["sudo", "systemctl", "is-active", "kimiproxy"],
            capture_output=True,
            text=True
        )
        if res.stdout.strip() != "active":
            subprocess.run(["sudo", "systemctl", "start", "kimiproxy"], capture_output=True)
            await asyncio.sleep(6)
    except Exception:
        pass
