import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "blue_horizon.db"


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def ensure_checkpoint_table() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS state_checkpoints (
                checkpoint_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                node_name TEXT NOT NULL,
                state_json TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.commit()


def save_checkpoint(
    run_id: str,
    node_name: str,
    state: dict[str, Any],
    status: str = "active",
) -> int:
    ensure_checkpoint_table()

    created_at = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO state_checkpoints
            (run_id, node_name, state_json, status, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                run_id,
                node_name,
                json.dumps(state, default=str),
                status,
                created_at,
            ),
        )
        connection.commit()

        return int(cursor.lastrowid)


def load_latest_checkpoint(run_id: str) -> dict[str, Any] | None:
    ensure_checkpoint_table()

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                checkpoint_id,
                run_id,
                node_name,
                state_json,
                status,
                created_at
            FROM state_checkpoints
            WHERE run_id = ?
            ORDER BY checkpoint_id DESC
            LIMIT 1
            """,
            (run_id,),
        ).fetchone()

    if row is None:
        return None

    return {
        "checkpoint_id": row["checkpoint_id"],
        "run_id": row["run_id"],
        "node_name": row["node_name"],
        "state": json.loads(row["state_json"]),
        "status": row["status"],
        "created_at": row["created_at"],
    }
