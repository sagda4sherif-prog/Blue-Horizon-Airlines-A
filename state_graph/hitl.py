from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import uuid

from .state import FlightRecoveryState


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "blue_horizon.db"


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def ensure_hitl_table() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS hitl_requests (
                request_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                node_name TEXT NOT NULL,
                reason TEXT NOT NULL,
                state_json TEXT NOT NULL,
                status TEXT NOT NULL,
                decision TEXT,
                created_at TEXT NOT NULL,
                resolved_at TEXT
            )
            """
        )
        connection.commit()


def create_hitl_request(
    state: FlightRecoveryState,
    node_name: str,
    reason: str,
) -> str:
    ensure_hitl_table()

    request_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    import json

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO hitl_requests (
                request_id,
                run_id,
                node_name,
                reason,
                state_json,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                state["run_id"],
                node_name,
                reason,
                json.dumps(dict(state), default=str),
                "pending",
                created_at,
            ),
        )
        connection.commit()

    return request_id


def resolve_hitl_request(
    request_id: str,
    decision: str,
) -> bool:
    ensure_hitl_table()

    resolved_at = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE hitl_requests
            SET
                status = 'resolved',
                decision = ?,
                resolved_at = ?
            WHERE request_id = ?
              AND status = 'pending'
            """,
            (
                decision,
                resolved_at,
                request_id,
            ),
        )
        connection.commit()

        return cursor.rowcount == 1


def get_hitl_request(request_id: str) -> dict | None:
    ensure_hitl_table()

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM hitl_requests
            WHERE request_id = ?
            """,
            (request_id,),
        ).fetchone()

    if row is None:
        return None

    return dict(row)
