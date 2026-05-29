import platform
import shutil
import asyncio
from automations.log import get_logger
from automations.state import save_event

logger = get_logger("daily_brief")

def run():
    disk = shutil.disk_usage("/")
    used_percent = round((disk.used / disk.total) * 100, 2)
    brief = {
        "system": platform.platform(),
        "disk_used_percent": used_percent,
    }
    logger.info("Daily brief generated: %s", brief)
    asyncio.run(save_event("daily_brief", brief))
    return brief

if __name__ == "__main__":
    run()

