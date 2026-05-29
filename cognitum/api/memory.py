from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from cognitum.core.memory_store import store_memory, search_all_memories

router = APIRouter(prefix="/memory", tags=["Memory"])

class MemoryStoreRequest(BaseModel):
    content: str = Field(..., description="The factual text or content to commit to memory")
    memory_type: str = Field("note.idea", description="The categorization type of the memory")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional associated metadata dict")

class MemoryStoreResponse(BaseModel):
    success: bool
    event_id: int

@router.get("/search")
async def search_memories(
    query: str = Query(..., description="Substring keyword to search for across database and vault"),
    limit_per_source: int = Query(5, description="Maximum results to return per source")
):
    """Searches memory vaults and transaction logs for matching concepts/events."""
    try:
        results = await search_all_memories(query, limit_per_source=limit_per_source)
        return {"query": query, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Memory search error: {e}")

@router.post("/store", response_model=MemoryStoreResponse)
async def ingest_memory(req: MemoryStoreRequest):
    """Stores a piece of knowledge, study log, or mistake into memory."""
    try:
        event_id = await store_memory(req.content, req.memory_type, req.metadata)
        return MemoryStoreResponse(success=True, event_id=event_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store memory: {e}")
