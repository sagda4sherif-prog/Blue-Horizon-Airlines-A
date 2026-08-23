# Platform API Contract

This is the document the prep-task list asked for: "meeting with Person 1
and 2 to document the API contracts in writing." It's written down instead
of just discussed so it survives past the meeting.

Read this if you're building `state_graph/` (Persons 1, 2, or 3) and need
to know exactly what to call so your graph's pauses and failures show up
on the platform.

## Important distinction: `elicitation.py` is NOT the final-project HITL

`mcp_server/elicitation.py` (`ctx.elicit(...)`) is MCP's own protocol-level
confirmation — it blocks a single tool call, waiting synchronously on
whoever is connected to that live MCP session, for as long as that
session stays open. It's a good fit for "are you sure?" inside one tool
call.

The final project's HITL requirement is a different mechanism: a graph
**pauses indefinitely** (hours, days), **persists its full checkpoint**,
and only resumes after **an admin acts through the platform**, possibly
in a completely different process than the one that paused. Don't
satisfy the HITL rubric item with `ctx.elicit` alone — route it through
`graph_bridge.create_hitl_request()` below instead.

## Import path (read this before copy-pasting an import)

The `platform/` folder shadows Python's stdlib `platform` module, so
never `import platform.backend.graph_bridge`. Instead, at the top of
your `state_graph/` entrypoint:

```python
import os, sys
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # adjust to your file's depth
sys.path.insert(0, os.path.join(REPO_ROOT, "platform"))

from backend.graph_bridge import (
    create_ticket,
    get_ticket_status,
    create_hitl_request,
    get_hitl_decision,
)
```

(`run_platform_backend.py` at the repo root does the same trick — copy
its sys.path lines if you want the exact pattern.)

## Tickets — unplanned failure

Call this the moment a node fails in a way a retry can't fix (tool
error, schema validation failure, unparseable model output) — NOT for
expected pauses, that's HITL below.

```python
ticket_id = create_ticket(
    graph_name="flight_compensation",   # your graph's name
    run_id=state["run_id"],             # so it can be resumed later
    node_name="submit_claim",           # which node failed
    failure_type="tool_error",          # short machine-ish label
    description="Insurer endpoint returned a malformed response.",
    checkpoint_state=state,             # full state dict — gets JSON-serialized
)
```

Your graph should stop advancing this run at this point. To find out
when an admin has resolved it (so you can resume from the checkpoint):

```python
status = get_ticket_status(ticket_id)  # "open" | "investigating" | "resolved" | None
```

Poll this (or re-check on your own retry/resume schedule) and only
re-enter the failed node once it comes back `"resolved"`.

## HITL — expected pause for a decision

Call this when a node hits a condition it must not decide alone (an
amount above threshold, an action against policy, confidence below a
bar):

```python
hitl_id = create_hitl_request(
    graph_name="flight_compensation",
    run_id=state["run_id"],
    node_name="approve_payout",
    reason="compensation_amount_exceeds_threshold",  # your defined condition
    summary=f"Approve ${state['amount']} payout for flight {state['flight_id']}?",
    checkpoint_state=state,
)
```

On resume, read back what the admin decided:

```python
decision = get_hitl_decision(hitl_id)
# None            -> still pending, stay paused
# {"status": "approved", "payload": {...}, "decided_by": "..."}
# {"status": "rejected", "payload": {...}, "decided_by": "..."}
```

`payload` is free-form JSON the admin can fill in from the platform UI —
use it for anything beyond a plain yes/no (e.g. an approved amount that
differs from what the graph proposed).

## RAG documents (Person 2)

The admin RAG page already writes to a `RagDocuments` table and calls
`OperationalRAGPipeline.add_document(title, content)` /
`.remove_document(title)` **if they exist**. They don't yet. Add them to
`rag/rag_pipeline.py` with these exact names and signatures and the
admin page will start actually re-indexing on the next request — no
platform-side changes needed:

```python
def add_document(self, title: str, content: str) -> None:
    ...  # chunk `content`, add to self.vector_store, update bm25_index

def remove_document(self, title: str) -> None:
    ...  # remove matching chunks from self.vector_store / bm25_index
```

## Tool registry (Person 1) — already wired, no action needed

`platform/backend/routers/tools.py` calls `tool_registry.register()` /
`.unregister()` directly — this already works against whatever's in
`mcp_server/tools.py` today. Nothing to change here unless the registry's
public method names change.

## Chat / agent switching

`platform/backend/chat_engine.py` currently exposes two working agents
(`operations`, general MCP tool-calling; `rag`, policy Q&A) and one
placeholder (`graph`, marked `available: false`). Once your three
state-graph agents have a callable entrypoint (a function that takes a
user message + run_id and returns a reply, or resumes a paused run),
tell Person 4 — wiring a new agent into `chat_engine.run_turn()` and
flipping its `available` flag in `list_agents()` is a small change.
