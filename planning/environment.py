"""EnvironmentFeedback sources for LATS / Reflexion.

The reference toolkit ships `Environment` as a stochastic evaluator that
ignores the candidate entirely (see `RandomEnvironment` below, kept only so
the "ungrounded vs. grounded" comparison in `planning_eval/` has something
real to compare against). Blue Horizon's planning agent ships with
`GroundedEnvironment` as the default: it answers "did this sub-task
actually succeed?" by reading Blue Horizon's real SQLite database
(`db/blue_horizon.db`) and applying the same operational rules the MCP
write tools enforce (`mcp_server/tools.py::assign_backup_crew`,
`assign_aircraft`) — an 8-hour crew duty-hour ceiling, crew availability,
aircraft maintenance status, and aircraft double-booking — instead of
asking the model whether it is happy with its own candidate.
"""

from __future__ import annotations

import random
import re
import sqlite3
from pathlib import Path

from .models import EnvironmentFeedback

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "db" / "blue_horizon.db"

_AIRCRAFT_RE = re.compile(r"aircraft\D{0,8}(\d+)", re.IGNORECASE)
_CREW_RE = re.compile(r"crew\D{0,8}(\d+)", re.IGNORECASE)
_FLIGHT_RE = re.compile(r"flight\D{0,8}(\d+)", re.IGNORECASE)

CREW_DUTY_HOUR_LIMIT = 8  # mirrors mcp_server/tools.py::assign_backup_crew


class GroundedEnvironment:
    """Checks a proposed reshuffle candidate against the real database."""

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH):
        self.db_path = str(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def evaluate(self, state: str) -> EnvironmentFeedback:
        aircraft_ids = [int(m) for m in _AIRCRAFT_RE.findall(state)]
        crew_ids = [int(m) for m in _CREW_RE.findall(state)]
        flight_ids = [int(m) for m in _FLIGHT_RE.findall(state)]

        if not aircraft_ids and not crew_ids:
            return EnvironmentFeedback(
                success=False,
                score=0.0,
                details=["No concrete aircraft_id or crew_id found in the candidate; nothing to verify."],
            )

        details: list[str] = []
        checks_passed = 0
        checks_total = 0

        try:
            conn = self._connect()
        except sqlite3.Error as exc:
            return EnvironmentFeedback(
                success=False, score=0.0, details=[f"Could not open Blue Horizon database: {exc}"]
            )

        try:
            for aircraft_id in aircraft_ids:
                checks_total += 1
                ok, reason = self._check_aircraft(conn, aircraft_id, flight_ids)
                details.append(reason)
                checks_passed += int(ok)

            for crew_id in crew_ids:
                checks_total += 1
                ok, reason = self._check_crew(conn, crew_id)
                details.append(reason)
                checks_passed += int(ok)
        finally:
            conn.close()

        score = checks_passed / checks_total if checks_total else 0.0
        success = checks_total > 0 and checks_passed == checks_total
        return EnvironmentFeedback(
            success=success,
            score=round(score, 4),
            details=[] if success else details,
        )

    @staticmethod
    def _check_aircraft(conn: sqlite3.Connection, aircraft_id: int, flight_ids: list[int]) -> tuple[bool, str]:
        row = conn.execute(
            "SELECT aircraft_id, status FROM Aircraft WHERE aircraft_id = ?",
            (aircraft_id,),
        ).fetchone()
        if row is None:
            return False, f"aircraft {aircraft_id}: does not exist"

        if row["status"] not in ("Available", "Assigned"):
            return False, f"aircraft {aircraft_id}: status is '{row['status']}', not usable for reassignment"

        open_maint = conn.execute(
            """
            SELECT severity, status FROM Maintenance
            WHERE aircraft_id = ? AND status IN ('Pending', 'In Progress')
            """,
            (aircraft_id,),
        ).fetchall()
        blocking = [m for m in open_maint if m["severity"] in ("High", "Critical")]
        if blocking:
            sev = blocking[0]["severity"]
            return False, f"aircraft {aircraft_id}: open {sev}-severity maintenance in progress"

        for flight_id in flight_ids:
            flight = conn.execute(
                "SELECT departure_time, arrival_time FROM Flights WHERE flight_id = ?",
                (flight_id,),
            ).fetchone()
            if flight is None:
                continue
            overlap = conn.execute(
                """
                SELECT f.flight_id FROM Flights f
                WHERE f.aircraft_id = ?
                  AND f.flight_id != ?
                  AND f.status NOT IN ('Cancelled', 'Completed')
                  AND f.departure_time < ? AND f.arrival_time > ?
                """,
                (aircraft_id, flight_id, flight["arrival_time"], flight["departure_time"]),
            ).fetchall()
            if overlap:
                return False, f"aircraft {aircraft_id}: already booked on an overlapping flight for flight {flight_id}"

        return True, f"aircraft {aircraft_id}: available and unblocked"

    @staticmethod
    def _check_crew(conn: sqlite3.Connection, crew_id: int) -> tuple[bool, str]:
        row = conn.execute(
            "SELECT availability, hours_flown_today FROM Crew WHERE crew_id = ?",
            (crew_id,),
        ).fetchone()
        if row is None:
            return False, f"crew {crew_id}: does not exist"
        if not row["availability"]:
            return False, f"crew {crew_id}: not available"
        if row["hours_flown_today"] >= CREW_DUTY_HOUR_LIMIT:
            return False, f"crew {crew_id}: at or over the {CREW_DUTY_HOUR_LIMIT}-hour duty limit ({row['hours_flown_today']}h flown)"
        return True, f"crew {crew_id}: available, {row['hours_flown_today']}h flown today"


class RandomEnvironment:
    """The toolkit's original stochastic evaluator (kept as the ungrounded control)."""

    def __init__(self, success_threshold: float = 0.6, rng: random.Random | None = None):
        if not 0.0 <= success_threshold <= 1.0:
            raise ValueError("success_threshold must be between zero and one")
        self.success_threshold = success_threshold
        self.rng = rng or random.Random()

    def evaluate(self, state: str) -> EnvironmentFeedback:
        del state  # This evaluator intentionally ignores the candidate contents.
        score = round(self.rng.betavariate(5.0, 2.0), 4)
        success = score >= self.success_threshold
        details = [] if success else ["The randomized evaluator rejected this attempt."]
        return EnvironmentFeedback(success=success, score=score, details=details)


# Backwards-compatible names: earlier revisions imported `Environment` as the
# default evaluator. The default is now the grounded one.
Environment = GroundedEnvironment