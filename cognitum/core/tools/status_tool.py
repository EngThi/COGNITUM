import subprocess
from pathlib import Path
from cognitum.config import settings

def get_status() -> str:
    """Returns the Cognitum health check status dashboard output."""
    try:
        script_path = Path(settings.base_dir) / "scripts" / "status_check.py"
        # Fallback to system path if repository file not executable/present
        if not script_path.exists():
            script_path = Path("/opt/automation/scripts/status_check.py")
            
        res = subprocess.run([str(script_path)], capture_output=True, text=True)
        return res.stdout.strip()
    except Exception as e:
        return f"Error checking status: {e}"
