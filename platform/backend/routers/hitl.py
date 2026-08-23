"""
Human-in-the-loop escalation queue.

REAL CRUD against HITLRequests. Creation happens from state_graph/ code
the moment a node hits a condition it isn't allowed to decide alone
(amount above threshold, action contradicts policy, confidence below
bar) — see graph_bridge.create_hitl_request() and API_CONTRACT.md.

decision_payload is intentionally free-form JSON (not just approve/
reject) so a graph's HITL node can ask for more than a binary — e.g.
"approved_amount": 350 instead of the model's proposed 500.
"""

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_connection

router = APIRouter(prefix="/api/hitl", tags=["hitl"])


class DecisionIn(BaseModel):
    approved: bool
    decided_by: str
    payload: dict = {}


@router.get("")
def list_hitl(status: str | None = "pending"):
    conn = get_connection()
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM HITLRequests WHERE status = ? ORDER BY created_at ASC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM HITLRequests ORDER BY created_at DESC"
            ).fetchall()

        return {"requests": [dict(row) for row in rows]}
    finally:
        conn.close()


@router.get("/{hitl_id}")
def get_hitl(hitl_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM HITLRequests WHERE hitl_id = ?", (hitl_id,)
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="HITL request not found")

        request = dict(row)

        try:
            request["checkpoint_state"] = json.loads(request["checkpoint_state"])
        except (TypeError, json.JSONDecodeError):
            pass

        return request
    finally:
        conn.close()


@router.post("/{hitl_id}/decide")
def decide(hitl_id: int, body: DecisionIn):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT hitl_id, status FROM HITLRequests WHERE hitl_id = ?",
            (hitl_id,),
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="HITL request not found")

        if row["status"] != "pending":
            raise HTTPException(
                status_code=409,
                detail=f"Request already {row['status']}",
            )

        conn.execute(
            """
            UPDATE HITLRequests
            SET status = ?,
                decision_payload = ?,
                decided_by = ?,
                decided_at = CURRENT_TIMESTAMP
            WHERE hitl_id = ?
            """,
            (
                "approved" if body.approved else "rejected",
                json.dumps(body.payload),
                body.decided_by,
                hitl_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "hitl_id": hitl_id,
        "status": "approved" if body.approved else "rejected",
    }
