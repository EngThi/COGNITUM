from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from cognitum.core.planner import generate_plan, Plan
from cognitum.core.profile_store import load_profile
from cognitum.core.policy_gate import load_policy
from cognitum.core.memory_store import search_all_memories

router = APIRouter(prefix="/plan", tags=["Planner"])

class PlanRequest(BaseModel):
    goal: str = Field(..., description="The objective or request to plan for")
    use_context: bool = Field(True, description="Inject user profile, memory context, and policies into the planner")

@router.post("", response_model=Plan)
async def create_plan(req: PlanRequest):
    """Generates a structured execution plan for achieving the user's goal, respecting safety policies."""
    try:
        profile_data = None
        policies_data = None
        context_str = ""
        
        if req.use_context:
            profile = load_profile()
            profile_data = profile.model_dump()
            
            policy = load_policy()
            policies_data = policy.model_dump()
            
            # Fetch memories related to the goal words
            keywords = " ".join([w for w in req.goal.split() if len(w) > 3])
            memories = await search_all_memories(keywords, limit_per_source=2)
            
            if memories:
                context_str = "Relevant memories retrieved:\n"
                for m in memories:
                    if m.get("source") == "database":
                        context_str += f"- [Event ID {m.get('id')}] Type: {m.get('type')}: {m.get('content')}\n"
                    else:
                        context_str += f"- [Vault File {m.get('file_path')}]: {m.get('content')}\n"
                        
        plan = await generate_plan(
            goal=req.goal,
            context=context_str if context_str else None,
            profile_data=profile_data,
            policies_data=policies_data
        )
        return plan
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Planning generation failed: {e}")
