"""
Durable checkpoint store shared by every graph. One table, namespaced by
`graph_name`, instead of each graph inventing its own — so a checkpoint
row always tells you which of the three graphs it belongs to.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CHECKPOINT_DB = PROJECT_ROOT / "db" / "state_graph_checkpoints.db"


def _connect() -> sqlite3.Connection:
    CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(CHECKPOINT_DB))
    connection.row_factory = sqlite3.Row
    return connection


def _initialize() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS state_graph_checkpoints (
                checkpoint_id TEXT PRIMARY KEY,
                graph_name TEXT NOT NULL,
                run_id TEXT NOT NULL,
                node_name TEXT NOT NULL,
                state_json TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.commit()


def save_checkpoint(
    graph_name: str,
    run_id: str,
    node_name: str,
    state: dict,
    status: str = "active",
) -> str:
    _initialize()
    checkpoint_id = str(uuid4())

    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO state_graph_checkpoints
                (checkpoint_id, graph_name, run_id, node_name, state_json, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                checkpoint_id,
                graph_name,
                run_id,
                node_name,
                json.dumps(state, ensure_ascii=False, default=str),
                status,
            ),
        )
        connection.commit()

    return checkpoint_id


def load_latest_checkpoint(graph_name: str, run_id: str) -> dict | None:
    _initialize()

    with _connect() as connection:
        row = connection.execute(
            """
            SELECT * FROM state_graph_checkpoints
            WHERE graph_name = ? AND run_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (graph_name, run_id),
        ).fetchone()

    if row is None:
        return None

    return {
        "checkpoint_id": row["checkpoint_id"],
        "graph_name": row["graph_name"],
        "run_id": row["run_id"],
        "node_name": row["node_name"],
        "state": json.loads(row["state_json"]),
        "status": row["status"],
        "created_at": row["created_at"],
    }
