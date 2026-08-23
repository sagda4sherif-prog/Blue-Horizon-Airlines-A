"""
Tickets (failure & recovery).

REAL CRUD against the Tickets table. Creation is meant to happen from
state_graph/ code the moment a node fails unexpectedly — see
graph_bridge.create_ticket() and platform/API_CONTRACT.md. This router
does not itself decide when something has "failed"; that judgment
belongs to the graph.
"""

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_connection

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


class ResolveIn(BaseModel):
    resolution_notes: str
    resolved_by: str


@router.get("")
def list_tickets(status: str | None = None):
    conn = get_connection()
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM Tickets WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM Tickets ORDER BY created_at DESC"
            ).fetchall()

        return {"tickets": [dict(row) for row in rows]}
    finally:
        conn.close()


@router.get("/{ticket_id}")
def get_ticket(ticket_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM Tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Ticket not found")

        ticket = dict(row)

        try:
            ticket["checkpoint_state"] = json.loads(ticket["checkpoint_state"])
        except (TypeError, json.JSONDecodeError):
            pass

        return ticket
    finally:
        conn.close()


@router.post("/{ticket_id}/investigate")
def mark_investigating(ticket_id: int):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE Tickets SET status = 'investigating' WHERE ticket_id = ?",
            (ticket_id,),
        )
        conn.commit()
    finally:
        conn.close()

    return {"ticket_id": ticket_id, "status": "investigating"}


@router.post("/{ticket_id}/resolve")
def resolve_ticket(ticket_id: int, body: ResolveIn):
    """
    Marks the ticket resolved. Actually RESUMING the graph run from its
    checkpoint is state_graph/'s responsibility (it owns the checkpoint
    store) — see graph_bridge.resume_run(run_id) in API_CONTRACT.md,
    which the graph side is expected to call after (or poll for) this
    status flip.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT ticket_id FROM Tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Ticket not found")

        conn.execute(
            """
            UPDATE Tickets
            SET status = 'resolved',
                resolution_notes = ?,
                resolved_by = ?,
                resolved_at = CURRENT_TIMESTAMP
            WHERE ticket_id = ?
            """,
            (body.resolution_notes, body.resolved_by, ticket_id),
        )
        conn.commit()
    finally:
        conn.close()

    return {"ticket_id": ticket_id, "status": "resolved"}
