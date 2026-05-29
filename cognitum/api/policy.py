from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any
from cognitum.core.policy_gate import load_policy, check_action_safety, Policy

router = APIRouter(prefix="/policy", tags=["Policy"])

class ActionCheckRequest(BaseModel):
    action_type: str = Field(..., description="Action type to evaluate (e.g. run_command, read_file, write_file)")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Parameters associated with the action")

class ActionCheckResponse(BaseModel):
    safe: bool
    reason: str

@router.get("", response_model=Policy)
async def get_policy():
    """Retrieves the active safety policy constraints (allowed/denied lists, quiet hours)."""
    try:
        return load_policy()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load policy: {e}")

@router.post("/check", response_model=ActionCheckResponse)
async def check_action(req: ActionCheckRequest):
    """Evaluates whether an action is safe to execute according to current policies."""
    try:
        safe, reason = check_action_safety(req.action_type, req.parameters)
        return ActionCheckResponse(safe=safe, reason=reason)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Policy gate evaluation error: {e}")
