"""
Single, shared entry point for talking to the platform from any graph in
state_graph/.

Every graph package (flight_recovery/, flight_compensation/,
crew_reassignment/) imports create_ticket / get_ticket_status /
create_hitl_request / get_hitl_decision from HERE, not from
platform.backend.graph_bridge directly. Two reasons:

1. `platform/` shadows Python's stdlib `platform` module, so the sys.path
   trick (adding <repo_root>/platform ahead of <repo_root>) has to happen
   exactly once, in exactly one place, before any of this is imported.
   Duplicating it per-graph is how it drifts and breaks.
2. Every prior graph in this project (flight_recovery's tickets, its HITL
   requests, and flight_compensation's HITL requests) independently wrote
   to its OWN local sqlite table instead of the platform's real Tickets /
   HITLRequests tables — so failures and approval requests never showed up
   in the admin UI. Routing everything through this one module is what
   prevents that regression from happening a fourth time.
"""

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PLATFORM_DIR = os.path.join(_REPO_ROOT, "platform")

for _path in (_REPO_ROOT, _PLATFORM_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from backend.db import ensure_platform_schema  # noqa: E402
from backend.graph_bridge import (  # noqa: E402
    create_hitl_request,
    create_ticket,
    get_hitl_decision,
    get_ticket_status,
)

# Tickets / HITLRequests only exist once ensure_platform_schema() has run.
# Previously that only happened when the FastAPI app started, so a graph
# invoked on its own (a test, a scheduled job, a script) before the
# platform backend had ever booted would hit "no such table". Applying it
# here, once, on import, means any graph run is self-sufficient. It's
# idempotent (CREATE TABLE IF NOT EXISTS), so this is safe to call even
# when the platform backend has already done it.
ensure_platform_schema()

__all__ = [
    "create_ticket",
    "get_ticket_status",
    "create_hitl_request",
    "get_hitl_decision",
]
