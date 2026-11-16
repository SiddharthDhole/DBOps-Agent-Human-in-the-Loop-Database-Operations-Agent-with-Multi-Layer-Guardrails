import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router

app = FastAPI(
    title="DBOps Agent API",
    description="Autonomous PostgreSQL Database Operations & Analytics Agent with Live Streaming and Guardrails",
    version="1.0.0",
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routes
app.include_router(router)

# Serve web UI
static_dir = Path(__file__).parent / "static"
index_file = static_dir / "index.html"


@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the interactive streaming Web UI."""
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>DBOps Agent API is running</h1>")


@app.get("/ui", response_class=HTMLResponse)
async def serve_ui_alias():
    """Alias for interactive Web UI."""
    return await serve_ui()
