import uvloop
import asyncio
import shutil
import psutil
import httpx
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel

# Set uvloop as the event loop policy
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

from automations.state import save_event, init_db
from automations.log import get_logger

logger = get_logger("api")

app = FastAPI(
    title="Automation Runtime",
    default_response_class=ORJSONResponse
)

http_client = httpx.AsyncClient(timeout=30.0)

class IdeaIn(BaseModel):
    source: str = "manual"
    text: str

class CognitiveEvent(BaseModel):
    type: str
    payload: dict

async def process_idea_async(idea: IdeaIn):
    await save_event("idea", idea.model_dump_json())
    logger.info("Idea saved: %s", idea.text)

@app.on_event("startup")
async def startup():
    await init_db()

@app.get("/health")
async def health():
    disk = shutil.disk_usage("/")
    memory = psutil.virtual_memory()

    return {
        "status": "ok",
        "memory_percent": memory.percent,
        "disk_percent": round((disk.used / disk.total) * 100, 2),
        "cpu_percent": psutil.cpu_percent()
    }

@app.post("/ideas")
async def capture_idea(idea: IdeaIn, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_idea_async, idea)
    return {"accepted": True}

@app.post("/ingest")
async def ingest_event(event: CognitiveEvent):
    event_id = await save_event(event.type, event.payload)
    logger.info("Event ingested: %s (ID: %d)", event.type, event_id)
    return {"accepted": True, "event_id": event_id}

@app.on_event("shutdown")
async def shutdown():
    await http_client.aclose()
