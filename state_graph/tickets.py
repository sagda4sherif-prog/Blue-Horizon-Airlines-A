from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
import uuid

from .state import FlightRecoveryState


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "blue_horizon.db"


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def ensure_ticket_table() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS recovery_tickets (
                ticket_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                node_name TEXT NOT NULL,
                error TEXT NOT NULL,
                state_json TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                resolved_at TEXT
            )
            """
        )
        connection.commit()


def create_ticket(
    state: FlightRecoveryState,
    node_name: str,
    error: str,
) -> str:
    ensure_ticket_table()

    ticket_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO recovery_tickets (
                ticket_id,
                run_id,
                node_name,
                error,
                state_json,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticket_id,
                state["run_id"],
                node_name,
                error,
                json.dumps(dict(state), default=str),
                "open",
                created_at,
            ),
        )
        connection.commit()

    return ticket_id


def resolve_ticket(ticket_id: str) -> bool:
    ensure_ticket_table()

    resolved_at = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE recovery_tickets
            SET
                status = 'resolved',
                resolved_at = ?
            WHERE ticket_id = ?
              AND status != 'resolved'
            """,
            (
                resolved_at,
                ticket_id,
            ),
        )
        connection.commit()

        return cursor.rowcount == 1


def get_ticket(ticket_id: str) -> dict | None:
    ensure_ticket_table()

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM recovery_tickets
            WHERE ticket_id = ?
            """,
            (ticket_id,),
        ).fetchone()

    if row is None:
        return None

    return dict(row)
