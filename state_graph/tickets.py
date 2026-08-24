from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TICKETS_DB = PROJECT_ROOT / "db" / "state_graph_tickets.db"


class TicketManager:
    def __init__(self, database_path: str | Path = TICKETS_DB):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self._initialize()

    def _connect(self):
        return sqlite3.connect(str(self.database_path))

    def _initialize(self):
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tickets (
                    ticket_id TEXT PRIMARY KEY,
                    flight_id INTEGER,
                    error_type TEXT NOT NULL,
                    error_message TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP
                )
                """
            )
            connection.commit()

    def create_ticket(
        self,
        flight_id: int | None,
        error_type: str,
        error_message: str,
    ) -> str:
        ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO tickets (
                    ticket_id,
                    flight_id,
                    error_type,
                    error_message,
                    status
                )
                VALUES (?, ?, ?, ?, 'open')
                """,
                (
                    ticket_id,
                    flight_id,
                    error_type,
                    error_message,
                ),
            )
            connection.commit()

        return ticket_id

    def update_status(
        self,
        ticket_id: str,
        status: str,
    ):
        allowed_statuses = {
            "open",
            "investigating",
            "resolved",
        }

        if status not in allowed_statuses:
            raise ValueError(
                f"Invalid ticket status: {status}"
            )

        with self._connect() as connection:
            if status == "resolved":
                connection.execute(
                    """
                    UPDATE tickets
                    SET status = ?,
                        resolved_at = CURRENT_TIMESTAMP
                    WHERE ticket_id = ?
                    """,
                    (status, ticket_id),
                )
            else:
                connection.execute(
                    """
                    UPDATE tickets
                    SET status = ?,
                        resolved_at = NULL
                    WHERE ticket_id = ?
                    """,
                    (status, ticket_id),
                )

            connection.commit()

    def get_ticket(self, ticket_id: str):
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row

            row = connection.execute(
                """
                SELECT *
                FROM tickets
                WHERE ticket_id = ?
                """,
                (ticket_id,),
            ).fetchone()

        return dict(row) if row else None

    def list_open_tickets(self):
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row

            rows = connection.execute(
                """
                SELECT *
                FROM tickets
                WHERE status != 'resolved'
                ORDER BY created_at ASC
                """
            ).fetchall()

        return [dict(row) for row in rows]
