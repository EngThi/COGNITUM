import subprocess

def get_status() -> str:
    """Returns the Cognitum health check status dashboard output."""
    try:
        res = subprocess.run(["/opt/automation/scripts/status_check.py"], capture_output=True, text=True)
        return res.stdout.strip()
    except Exception as e:
        return f"Error checking status: {e}"
