"""
Reuses the SAME db/blue_horizon.db that mcp_server/database.py uses —
the platform is a second door into the same building, not a new one.

On import, additively applies platform_schema.sql (Tickets, HITLRequests,
RagDocuments). This never touches the core schema owned by Person 1.
"""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "db" / "blue_horizon.db"
PLATFORM_SCHEMA_PATH = Path(__file__).resolve().parent / "platform_schema.sql"


def get_connection() -> sqlite3.Connection:
    # Mirrors mcp_server/database.py's get_connection(): sqlite3.connect()
    # does NOT create missing parent directories, so on a fresh checkout
    # (no db/ yet) this raised "unable to open database file" the moment
    # the platform started, before the MCP server ever got a chance to
    # create it first.
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_platform_schema() -> None:
    conn = get_connection()
    try:
        conn.executescript(PLATFORM_SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()
