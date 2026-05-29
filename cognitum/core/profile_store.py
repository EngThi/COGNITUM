import yaml
from pathlib import Path
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from cognitum.config import settings

class Profile(BaseModel):
    name: str = "Thiago"
    timezone: str = "America/Sao_Paulo"
    preferences: Dict[str, Any] = Field(
        default_factory=lambda: {
            "explanations": "Portuguese",
            "verbosity": "medium"
        }
    )
    objectives: List[str] = Field(
        default_factory=lambda: [
            "Upgrade and stabilize COGNITUM layer",
            "Integrate clean cognitive routines in HOMES ecosystem"
        ]
    )

def get_profile_path() -> Path:
    return Path(settings.profiles_dir) / "default.yaml"

def load_profile() -> Profile:
    """Loads default user profile from YAML. Creates a default template if missing."""
    path = get_profile_path()
    if not path.exists():
        default_profile = Profile()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(default_profile.model_dump(), f, sort_keys=False)
        except Exception:
            pass
        return default_profile
        
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            return Profile.model_validate(data)
    except Exception:
        # Fallback to defaults on error
        return Profile()

def save_profile(profile: Profile) -> None:
    """Saves the user profile to default.yaml."""
    path = get_profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(profile.model_dump(), f, sort_keys=False)
