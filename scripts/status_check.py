#!/opt/automation/.venv/bin/python3
import os
import json
import sqlite3
import shutil
import psutil
from pathlib import Path

VAULT_DIR = Path("/opt/automation/vault")
DATABASE_PATH = "/opt/automation/runtime/state/automation.db"

def get_stats():
    # 1. System Health
    disk = shutil.disk_usage("/")
    memory = psutil.virtual_memory()
    system_health = {
        "ram_percent": memory.percent,
        "disk_percent": round((disk.used / disk.total) * 100, 2),
        "cpu_percent": psutil.cpu_percent()
    }
    
    # 2. Database stats
    total_events = 0
    pending_events = 0
    failed_events = 0
    failed_details = []
    due_reviews = 0
    
    if os.path.exists(DATABASE_PATH):
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Total events
            cursor.execute("SELECT COUNT(*) as count FROM events")
            total_events = cursor.fetchone()["count"]
            
            # Pending events (no 'processed' status for key workers)
            cursor.execute("""
                SELECT COUNT(DISTINCT e.id) as count FROM events e
                LEFT JOIN processed_events p ON e.id = p.event_id
                WHERE p.status IS NULL OR p.status = 'pending'
            """)
            pending_events = cursor.fetchone()["count"]
            
            # Failed events
            cursor.execute("""
                SELECT event_id, worker_name, error, updated_at 
                FROM processed_events 
                WHERE status = 'failed'
            """)
            failed_rows = cursor.fetchall()
            failed_events = len(failed_rows)
            for row in failed_rows:
                failed_details.append({
                    "event_id": row["event_id"],
                    "worker": row["worker_name"],
                    "error": row["error"],
                    "time": row["updated_at"]
                })
                
            # Due reviews
            cursor.execute("SELECT COUNT(*) as count FROM flashcards_state WHERE next_review <= CURRENT_TIMESTAMP")
            due_reviews = cursor.fetchone()["count"]
            
            conn.close()
        except Exception as e:
            failed_details.append({"error": f"Database access error: {e}"})

    # 3. Vault counts
    vault_notes = 0
    for folder in ["00-inbox", "01-concepts", "02-sessions", "03-mistakes"]:
        folder_path = VAULT_DIR / folder
        if folder_path.exists():
            vault_notes += len(list(folder_path.glob("*.md")))
            
    return {
        "system": system_health,
        "events": {
            "total": total_events,
            "pending": pending_events,
            "failed_count": failed_events,
            "failed_details": failed_details
        },
        "spaced_repetition": {
            "due_count": due_reviews
        },
        "vault": {
            "total_notes": vault_notes
        }
    }

def print_dashboard():
    stats = get_stats()
    sys = stats["system"]
    ev = stats["events"]
    sr = stats["spaced_repetition"]
    v = stats["vault"]
    
    print("=" * 60)
    print("🧠 COGNITUM RUNTIME SYSTEM OBSERVABILITY DASHBOARD")
    print("=" * 60)
    print(f"🖥️  SYSTEM HEALTH:")
    print(f"   • CPU Usage:    {sys['cpu_percent']}%")
    print(f"   • RAM Usage:    {sys['ram_percent']}%")
    print(f"   • Disk Usage:   {sys['disk_percent']}%")
    print("-" * 60)
    print(f"📊 EVENT PIPELINE:")
    print(f"   • Total Events: {ev['total']}")
    print(f"   • Pending:      {ev['pending']}")
    print(f"   • Failed:       {ev['failed_count']}")
    print("-" * 60)
    print(f"📚 MEMORY VAULT:")
    print(f"   • Notes Written: {v['total_notes']}")
    print(f"   • Flashcards Due: {sr['due_count']}")
    print("=" * 60)
    
    if ev["failed_details"]:
        print("⚠️  FAILED EVENTS (DEAD-LETTER QUEUE):")
        for detail in ev["failed_details"]:
            if "event_id" in detail:
                print(f"   [ID {detail['event_id']}] Worker: {detail['worker']}")
                print(f"   Error: {detail['error']}")
                print(f"   Time:  {detail['time']}")
                print("-" * 30)
            else:
                print(f"   Error: {detail['error']}")

if __name__ == "__main__":
    print_dashboard()
