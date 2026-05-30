import yaml
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple
from datetime import datetime
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field
from cognitum.config import settings

class Policy(BaseModel):
    allowed_commands: List[str] = Field(
        default_factory=lambda: [
            "ls", "git status", "git log", "python3 --version", "df -h", "free -m"
        ]
    )
    denied_commands: List[str] = Field(
        default_factory=lambda: [
            "rm -rf /", "rm -rf *", "mkfs", "dd if=", "shutdown", "reboot", "passwd"
        ]
    )
    restricted_hours: Dict[str, str] = Field(
        default_factory=lambda: {
            "start": "22:30",
            "end": "06:10"
        }
    )
    safety_gate_enabled: bool = True
    allow_sudo: bool = False
    enforce_workspace_containment: bool = True

def get_policy_path() -> Path:
    return Path(settings.policies_dir) / "default.yaml"

def load_policy() -> Policy:
    """Loads the safety policy from YAML. Creates a default template if missing."""
    path = get_policy_path()
    if not path.exists():
        default_policy = Policy()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(default_policy.model_dump(), f, sort_keys=False)
        except Exception:
            pass
        return default_policy
        
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            return Policy.model_validate(data)
    except Exception:
        # Fallback to default policy on error
        return Policy()

def is_in_restricted_hours(policy: Policy) -> bool:
    """Checks if current time is within the configured restricted hours."""
    try:
        tz = ZoneInfo(settings.timezone)
        now = datetime.now(tz).time()
        
        start_str = policy.restricted_hours.get("start", "22:30")
        end_str = policy.restricted_hours.get("end", "06:10")
        
        start_time = datetime.strptime(start_str, "%H:%M").time()
        end_time = datetime.strptime(end_str, "%H:%M").time()
        
        now_mins = now.hour * 60 + now.minute
        start_mins = start_time.hour * 60 + start_time.minute
        end_mins = end_time.hour * 60 + end_time.minute
        
        if start_mins > end_mins:  # Crosses midnight
            return now_mins >= start_mins or now_mins <= end_mins
        else:
            return start_mins <= now_mins <= end_mins
    except Exception:
        return False

def check_action_safety(action_type: str, parameters: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Evaluates an action (e.g. run_command, read_file, write_file) against active policies.
    Returns (is_safe, explanation_reason).
    """
    policy = load_policy()
    if not policy.safety_gate_enabled:
        return True, "Safety gate is disabled."

    # Command safety check. Hard-denied commands take precedence over contextual
    # checks so callers/tests get a deterministic explanation for dangerous input.
    if action_type == "run_command":
        cmd = parameters.get("command", "").strip()
        if not cmd:
            return False, "Empty command string."

        # Sudo check
        if not policy.allow_sudo and ("sudo " in cmd or cmd.startswith("sudo")):
            return False, "Action blocked: Sudo commands are prohibited by policy."

        # Denied command/keywords check
        for denied in policy.denied_commands:
            if denied in cmd:
                return False, f"Action blocked: Command contains forbidden keyword '{denied}'."

    # Time checks
    if is_in_restricted_hours(policy):
        # Allow reading, but restrict changes/execution during restricted hours
        if action_type in ["run_command", "write_file"]:
            return False, f"Action blocked: execution restricted during quiet hours ({policy.restricted_hours.get('start')} - {policy.restricted_hours.get('end')})."

    # Path containment check (read/write safety)
    elif action_type in ["read_file", "write_file"]:
        path_str = parameters.get("path", "").strip()
        if not path_str:
            return False, "Empty path string."
            
        if policy.enforce_workspace_containment:
            try:
                resolved_path = Path(path_str).resolve()
                # Must reside inside the workspace settings (base_dir or vault_dir or memory_dir)
                workspace_paths = [
                    Path(settings.base_dir).resolve(),
                    Path(settings.vault_dir).resolve(),
                    Path(settings.memory_dir).resolve()
                ]
                
                # Allow reading system configurations if not writing, but keep containment for writes
                if action_type == "write_file":
                    is_contained = any(resolved_path.is_relative_to(wp) for wp in workspace_paths)
                    if not is_contained:
                        return False, f"Action blocked: Attempted write outside designated workspace boundaries."
                else:  # read_file
                    # Allow reading workspace files and system checks (like /etc/hosts or systemctl status, but block sensitive etc/passwd read)
                    is_contained = any(resolved_path.is_relative_to(wp) for wp in workspace_paths)
                    if not is_contained:
                        # Extra security check for common sensitive files
                        if any(sensitive in str(resolved_path) for sensitive in ["etc/passwd", ".ssh/", "id_rsa"]):
                            return False, f"Action blocked: Attempted read of sensitive system files."
            except Exception as e:
                return False, f"Action blocked: Invalid path evaluation: {e}"

    return True, "Action approved by policy gate."
