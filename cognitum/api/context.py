import shutil
import psutil
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from cognitum.config import settings
from cognitum.core.profile_store import load_profile
from cognitum.core.policy_gate import load_policy
from cognitum.core.memory_store import search_all_memories
from cognitum.core.state import get_unprocessed_events

router = APIRouter(prefix="/context", tags=["Context"])

class ContextRequest(BaseModel):
    query: Optional[str] = Field(None, description="Optional search query to pull relevant memory items")

class ContextResponse(BaseModel):
    profile: Dict[str, Any]
    policy: Dict[str, Any]
    system_metrics: Dict[str, Any]
    memories: List[Dict[str, Any]]
    unprocessed_events_count: int

@router.post("", response_model=ContextResponse)
async def assemble_context(req: ContextRequest):
    """Assembles a unified context snapshot of the personal OS state (profile, rules, system stats, memories)."""
    try:
        # 1. Profile
        prof = load_profile()
        
        # 2. Policy
        pol = load_policy()
        
        # 3. System Metrics
        disk = shutil.disk_usage("/")
        memory = psutil.virtual_memory()
        system_stats = {
            "cpu_percent": psutil.cpu_percent(),
            "ram_percent": memory.percent,
            "disk_percent": round((disk.used / disk.total) * 100, 2)
        }
        
        # 4. Memories
        mems = []
        if req.query:
            mems = await search_all_memories(req.query, limit_per_source=3)
        else:
            # default: pull recent memories by searching empty query or empty list
            mems = await search_all_memories("", limit_per_source=2)
            
        # 5. Pending events count
        pending_events = await get_unprocessed_events("ai_router")
        pending_count = len(pending_events)
        
        return ContextResponse(
            profile=prof.model_dump(),
            policy=pol.model_dump(),
            system_metrics=system_stats,
            memories=mems,
            unprocessed_events_count=pending_count
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Context assembly error: {e}")
