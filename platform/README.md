# Blue Horizon Airlines — Web Platform

Person 4's deliverable: the admin dashboard and user chat surface that
sits in front of the shared `mcp_server/`, `db/`, `rag/`, and (once built)
`state_graph/`.

- `backend/` — FastAPI bridge. Talks to the real `mcp_server.tool_registry`,
  the real `rag/rag_pipeline.py`, and spawns the real `mcp_server/server.py`
  over stdio for chat — it does not reimplement any of that.
- `frontend/` — Next.js app. User-facing agent chat + admin dashboard
  (tool management, RAG documents, tickets, HITL queue).
- `API_CONTRACT.md` — what `state_graph/` (Persons 1/2/3) needs to call
  to make tickets and HITL requests show up here for real.

## Running it

**1. Backend** (from the repo root):

```bash
pip install -r requirements.txt
python run_platform_backend.py
```

Runs on `http://localhost:8001`. Needs `ANTHROPIC_API_KEY` and
`GEMINI_API_KEY` in `.env` (see `.env_example`) for the chat agents.

Don't run this with `uvicorn platform.backend.main:app` — see the
docstring in `run_platform_backend.py` for why (the `platform/` folder
name collides with Python's stdlib `platform` module).

**2. (Optional) seed demo data**, so Tickets/HITL aren't empty before
`state_graph/` exists:

```bash
python platform/backend/seed_demo.py
```

**3. Frontend**:

```bash
cd platform/frontend
npm install
npm run dev
```

Runs on `http://localhost:3000`. `/` is the user chat, `/admin` is the
admin dashboard. API calls are proxied to `:8001` via `next.config.js`,
so no CORS setup needed in dev.

## What's real vs. pending

| Feature | Status |
|---|---|
| Register/unregister MCP tools from the admin panel | **Real** — hits the live `tool_registry` |
| Chat with the "operations" agent | **Real** — Anthropic + live MCP tools |
| Chat with the "rag" (policy) agent | **Real** — uses `rag_pipeline.hybrid_search` |
| Add/remove RAG documents | **Real CRUD**, but not yet reflected in retrieval until Person 2 adds `add_document`/`remove_document` to the pipeline (falls back gracefully — see `API_CONTRACT.md`) |
| Tickets / HITL queue | **Real CRUD + UI**, but populated by seed data until `state_graph/` exists and calls `graph_bridge.py` (see `API_CONTRACT.md`) |
| Chat with state-graph agents | **Not yet** — shown grayed out in the UI with an explicit reason, not silently hidden |

## Crash-and-resume demo (once state_graph/ exists)

This platform's job in that demo is only the "surface it to a human"
half — the checkpoint store and the actual resume-from-checkpoint
mechanics belong to `state_graph/`. What this platform proves is: kill
the graph process mid-run → a ticket or HITL request created before the
kill is still sitting here, inspectable, exactly as it was → resolving
it here is what state_graph/ polls for before resuming.
