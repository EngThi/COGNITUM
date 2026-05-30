import uvloop
import asyncio
import signal
import shutil
import psutil
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel

# Set uvloop as the event loop policy
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

from cognitum.config import settings
from cognitum.core.state import init_db, save_event
from cognitum.core.log import get_logger
from cognitum.api.profile import router as profile_router
from cognitum.api.policy import router as policy_router
from cognitum.api.memory import router as memory_router
from cognitum.api.context import router as context_router
from cognitum.api.plan import router as plan_router

# Lifespan manager for FastAPI (replaces deprecated on_event('startup')/'shutdown')
http_client = None
logger = get_logger("main")
_mcp_signal_handlers_registered = False


def _register_mcp_signal_handlers() -> None:
    global _mcp_signal_handlers_registered
    if _mcp_signal_handlers_registered:
        return

    loop = asyncio.get_running_loop()

    async def _shutdown_mcp() -> None:
        from cognitum.core.mcp_client import shutdown_all

        await shutdown_all()

    for sig in (signal.SIGTERM, signal.SIGINT):
        previous_handler = signal.getsignal(sig)

        def _handler(signum, frame, *, previous=previous_handler) -> None:
            try:
                loop.call_soon_threadsafe(lambda: loop.create_task(_shutdown_mcp()))
            except RuntimeError:
                pass

            if callable(previous):
                previous(signum, frame)
            elif previous == signal.SIG_DFL:
                if signum == signal.SIGINT:
                    raise KeyboardInterrupt
                raise SystemExit(0)

        try:
            signal.signal(sig, _handler)
        except (ValueError, RuntimeError):
            logger.warning(f"Could not register MCP shutdown handler for {sig.name}")

    _mcp_signal_handlers_registered = True

@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    # Startup actions
    await init_db()
    try:
        from cognitum.core.tool_router import MCP_SERVERS_DEFAULT, init_tool_router

        await init_tool_router(MCP_SERVERS_DEFAULT)
    except Exception as exc:
        logger.warning(f"MCP ToolRouter initialization failed; continuing without MCP tools: {exc}")

    _register_mcp_signal_handlers()
    http_client = httpx.AsyncClient(timeout=settings.http_timeout)
    try:
        yield
    finally:
        # Shutdown actions
        try:
            from cognitum.core.mcp_client import shutdown_all

            await shutdown_all()
        except Exception as exc:
            logger.warning(f"MCP shutdown failed: {exc}")

        if http_client:
            await http_client.aclose()

app = FastAPI(
    title="COGNITUM — Cognition Layer",
    description="Production-safe Cognition Layer for the HOMES ecosystem",
    version="1.0.0",
    default_response_class=ORJSONResponse,
    lifespan=lifespan
)

# Register Cognitive API Routers
app.include_router(profile_router)
app.include_router(policy_router)
app.include_router(memory_router)
app.include_router(context_router)
app.include_router(plan_router)

# Legacy Request Schemas
class IdeaIn(BaseModel):
    source: str = "manual"
    text: str

class CognitiveEvent(BaseModel):
    type: str
    payload: dict

async def process_idea_async(idea: IdeaIn):
    await save_event("idea", idea.model_dump_json())

# Legacy /health endpoint containing system metrics
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

# Legacy endpoints maintained for backwards compatibility
@app.post("/ideas")
async def capture_idea(idea: IdeaIn, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_idea_async, idea)
    return {"accepted": True}

@app.post("/ingest")
async def ingest_event(event: CognitiveEvent):
    event_id = await save_event(event.type, event.payload)
    return {"accepted": True, "event_id": event_id}
