"""
Don't launch this with `uvicorn platform.backend.main:app` â€” the folder
is named `platform/` (per the project brief), which shadows Python's
own stdlib `platform` module if it's ever imported as a dotted package
from the repo root. Use the run script instead, which puts
`<repo>/platform` (not `<repo>`) on sys.path so this loads as the
top-level package `backend`, never as `platform.backend`:

    python run_platform_backend.py

The MCP server itself must be runnable at mcp_server/server.py (it is â€”
chat_engine spawns it over stdio per turn, same as agent/client.py does).
The web platform talks to Python over this FastAPI layer; it does not
reimplement anything mcp_server/, rag/, or agent/ already do.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import ensure_platform_schema
from .routers import tools, rag, tickets, hitl, chat

app = FastAPI(title="Blue Horizon Airlines â€” Ops Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    ensure_platform_schema()


app.include_router(tools.router)
app.include_router(rag.router)
app.include_router(tickets.router)
app.include_router(hitl.router)
app.include_router(chat.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/")
def root():
    return {
        "name": "Blue Horizon Airlines - Ops Platform API",
        "status": "running",
        "docs": "/docs",
        "health": "/api/health",
    }
