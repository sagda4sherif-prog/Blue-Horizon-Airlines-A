"""
The one file Persons 1/2/3 need to import from state_graph/ to talk to
the platform. Deliberately plain functions over sqlite3 (no FastAPI
dependency) so graph code can call these synchronously from inside a
LangGraph node without running an HTTP client.

Usage from inside a graph node. Note the import path: don't write
`from platform.backend.graph_bridge import ...` — see the big comment
in run_platform_backend.py for why (it collides with Python's stdlib
`platform` module). Instead, add `<repo_root>/platform` to sys.path
once (state_graph/'s own entrypoint can do this the same way
run_platform_backend.py does) and then:

    from backend.graph_bridge import create_ticket

    def some_node(state):
        try:
            ...
        except SomeToolError as e:
            create_ticket(
                graph_name="flight_compensation",
                run_id=state["run_id"],
                node_name="submit_claim",
                failure_type="tool_error",
                description=str(e),
                checkpoint_state=state,
            )
            return  # graph pauses here; admin resolves via the platform

For HITL:

    from platform.backend.graph_bridge import create_hitl_request, get_hitl_decision

    def approval_node(state):
        hitl_id = create_hitl_request(
            graph_name="flight_compensation",
            run_id=state["run_id"],
            node_name="approve_payout",
            reason="compensation_amount_exceeds_threshold",
            summary=f"Approve ${state['amount']} payout for flight {state['flight_id']}?",
            checkpoint_state=state,
        )
        # graph pauses; on resume, re-enter this node and call:
        decision = get_hitl_decision(hitl_id)
        if decision is None:
            return  # still pending, stay paused
        if decision["status"] == "approved":
            ...

Resuming the actual LangGraph run (reading the checkpoint back and
re-invoking the graph) is state_graph/'s job — this module only tracks
the request/ticket and the admin's decision, not the resumption
mechanics, since only the graph side owns the LangGraph checkpointer.
"""

import json

from .db import get_connection


def create_ticket(
    *,
    graph_name: str,
    run_id: str,
    node_name: str | None,
    failure_type: str,
    description: str,
    checkpoint_state: dict,
) -> int:
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO Tickets
                (graph_name, run_id, node_name, failure_type, description, checkpoint_state)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                graph_name,
                run_id,
                node_name,
                failure_type,
                description,
                json.dumps(checkpoint_state, default=str),
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_ticket_status(ticket_id: int) -> str | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT status FROM Tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        return row["status"] if row else None
    finally:
        conn.close()


def create_hitl_request(
    *,
    graph_name: str,
    run_id: str,
    node_name: str | None,
    reason: str,
    summary: str,
    checkpoint_state: dict,
) -> int:
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO HITLRequests
                (graph_name, run_id, node_name, reason, summary, checkpoint_state)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                graph_name,
                run_id,
                node_name,
                reason,
                summary,
                json.dumps(checkpoint_state, default=str),
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_hitl_decision(hitl_id: int) -> dict | None:
    """Returns None while still pending, else the recorded decision."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT status, decision_payload, decided_by FROM HITLRequests WHERE hitl_id = ?",
            (hitl_id,),
        ).fetchone()

        if row is None or row["status"] == "pending":
            return None

        return {
            "status": row["status"],
            "payload": json.loads(row["decision_payload"] or "{}"),
            "decided_by": row["decided_by"],
        }
    finally:
        conn.close()
