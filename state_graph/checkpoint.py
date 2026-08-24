from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from state_graph.compensation_state import CompensationState


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHECKPOINT_DB = PROJECT_ROOT / "db" / "state_graph_checkpoints.db"


class CompensationCheckpoint:
    def __init__(
        self,
        database_path: str | Path = CHECKPOINT_DB,
    ):
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
                CREATE TABLE IF NOT EXISTS compensation_checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    flight_id INTEGER,
                    current_node TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.commit()

    def save(self, state: CompensationState):
        payload = json.dumps(
            asdict(state),
            ensure_ascii=False,
        )

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO compensation_checkpoints
                (flight_id, current_node, state_json)
                VALUES (?, ?, ?)
                """,
                (
                    state.flight_id,
                    state.current_node,
                    payload,
                ),
            )
            connection.commit()

    def load_latest(
        self,
        flight_id: int,
    ) -> CompensationState | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT state_json
                FROM compensation_checkpoints
                WHERE flight_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (flight_id,),
            ).fetchone()

        if row is None:
            return None

        data = json.loads(row[0])

        return CompensationState(**data)
