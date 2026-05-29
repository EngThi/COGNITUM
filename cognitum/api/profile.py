from fastapi import APIRouter, HTTPException
from cognitum.core.profile_store import load_profile, save_profile, Profile

router = APIRouter(prefix="/profile", tags=["Profile"])

@router.get("", response_model=Profile)
async def get_profile():
    """Retrieves the active user profile details (preferences, timezone, objectives)."""
    try:
        return load_profile()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load profile: {e}")

@router.post("", response_model=Profile)
async def update_profile(profile: Profile):
    """Updates the user profile configuration."""
    try:
        save_profile(profile)
        return profile
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save profile: {e}")
