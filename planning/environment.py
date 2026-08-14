"""Grounded environment feedback for Blue Horizon flight planning.

This module is the domain adapter around the planning algorithms.  The
reference planning toolkit exposes a swappable Environment interface; here
we replace its randomized evaluator with deterministic checks against the
Blue Horizon SQLite database used by the MCP server.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from mcp_server.database import get_connection, initialize_database


@dataclass
class EnvironmentFeedback:
    valid: bool
    score: float
    reasons: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)


class GroundedFlightEnvironment:
    """Validate proposed operational actions against live database state."""

    OPEN_FLIGHT_STATUSES = {"Scheduled", "Delayed", "Rescheduled"}

    def __init__(self, connection_factory=get_connection):
        self.connection_factory = connection_factory
        initialize_database()

    def _fetchone(self, query: str, params: tuple[Any, ...] = ()):
        with self.connection_factory() as conn:
            return conn.execute(query, params).fetchone()

    def resolve_flight_id(self, request: str, default: int = 1) -> int:
        """Resolve a flight number such as BH218 to its database id."""
        text = request.upper()
        with self.connection_factory() as conn:
            rows = conn.execute(
                "SELECT flight_id, flight_number FROM Flights"
            ).fetchall()
        for row in rows:
            if row["flight_number"].upper() in text:
                return int(row["flight_id"])
        return default

    def snapshot(self, flight_id: int) -> dict[str, Any]:
        """Return the current operational state used for planning."""
        with self.connection_factory() as conn:
            flight = conn.execute(
                """
                SELECT f.flight_id, f.flight_number, f.departure_time,
                       f.arrival_time, f.status, f.aircraft_id,
                       f.origin_airport_id, f.destination_airport_id,
                       a.aircraft_id AS assigned_aircraft_id,
                       a.status AS aircraft_status,
                       a.capacity AS aircraft_capacity
                FROM Flights f
                LEFT JOIN Aircraft a ON a.aircraft_id = f.aircraft_id
                WHERE f.flight_id = ?
                """,
                (flight_id,),
            ).fetchone()
            if not flight:
                raise ValueError(f"Flight {flight_id} not found")

            crew = conn.execute(
                """
                SELECT c.crew_id, c.name, c.role, c.availability,
                       c.hours_flown_today
                FROM Crew c
                ORDER BY c.crew_id
                """
            ).fetchall()

            aircraft = conn.execute(
                """
                SELECT aircraft_id, tail_number, model, capacity, status,
                       current_airport_id
                FROM Aircraft
                ORDER BY aircraft_id
                """
            ).fetchall()

            maintenance = conn.execute(
                """
                SELECT maintenance_id, aircraft_id, severity, status
                FROM Maintenance
                WHERE status IN ('Pending', 'In Progress')
                """
            ).fetchall()

        return {
            "flight": dict(flight),
            "crew": [dict(row) for row in crew],
            "aircraft": [dict(row) for row in aircraft],
            "maintenance": [dict(row) for row in maintenance],
        }

    def available_aircraft(self) -> list[int]:
        """Return aircraft that are actually available and not under maintenance."""
        with self.connection_factory() as conn:
            rows = conn.execute(
                """
                SELECT a.aircraft_id
                FROM Aircraft a
                WHERE a.status = 'Available'
                  AND NOT EXISTS (
                      SELECT 1 FROM Maintenance m
                      WHERE m.aircraft_id = a.aircraft_id
                        AND m.status IN ('Pending', 'In Progress')
                  )
                ORDER BY a.aircraft_id
                """
            ).fetchall()
        return [int(row["aircraft_id"]) for row in rows]

    def available_crew(self) -> list[int]:
        """Return crew who are globally available and below the duty limit."""
        with self.connection_factory() as conn:
            rows = conn.execute(
                """
                SELECT crew_id
                FROM Crew
                WHERE availability = 1
                  AND hours_flown_today < 8
                ORDER BY crew_id
                """
            ).fetchall()
        return [int(row["crew_id"]) for row in rows]

    def available_crew_for_flight(self, flight_id: int) -> list[int]:
        """Return crew that are available and not already assigned to a flight."""
        with self.connection_factory() as conn:
            rows = conn.execute(
                """
                SELECT c.crew_id
                FROM Crew c
                WHERE c.availability = 1
                  AND c.hours_flown_today < 8
                  AND NOT EXISTS (
                      SELECT 1
                      FROM FlightCrew fc
                      WHERE fc.flight_id = ?
                        AND fc.crew_id = c.crew_id
                  )
                ORDER BY c.crew_id
                """,
                (flight_id,),
            ).fetchall()
        return [int(row["crew_id"]) for row in rows]

    @staticmethod
    def _action_type(action: dict[str, Any]) -> str:
        return str(action.get("type", "")).strip().lower()

    def validate_action(self, action: dict[str, Any]) -> EnvironmentFeedback:
        """Validate one proposed action using database truth."""
        flight_id = action.get("flight_id")
        if flight_id is None:
            return EnvironmentFeedback(False, 0.0, ["flight_id is required"])

        with self.connection_factory() as conn:
            flight = conn.execute(
                "SELECT * FROM Flights WHERE flight_id = ?", (flight_id,)
            ).fetchone()
            if not flight:
                return EnvironmentFeedback(False, 0.0, ["Flight not found"])

            checks: dict[str, bool] = {"flight_exists": True}
            reasons: list[str] = []
            action_type = self._action_type(action)

            checks["flight_open"] = flight["status"] in self.OPEN_FLIGHT_STATUSES
            if not checks["flight_open"]:
                reasons.append("Flight is cancelled or completed")

            if action_type == "assign_aircraft":
                aircraft_id = action.get("aircraft_id")
                aircraft = conn.execute(
                    "SELECT * FROM Aircraft WHERE aircraft_id = ?",
                    (aircraft_id,),
                ).fetchone()
                checks["aircraft_exists"] = aircraft is not None
                checks["aircraft_available"] = bool(
                    aircraft and aircraft["status"] == "Available"
                )
                checks["not_in_maintenance"] = bool(
                    aircraft
                    and not conn.execute(
                        """
                        SELECT 1 FROM Maintenance
                        WHERE aircraft_id = ?
                          AND status IN ('Pending', 'In Progress')
                        """,
                        (aircraft_id,),
                    ).fetchone()
                )
                if not checks["aircraft_exists"]:
                    reasons.append("Aircraft not found")
                if not checks["aircraft_available"]:
                    reasons.append("Aircraft is not available")
                if not checks["not_in_maintenance"]:
                    reasons.append("Aircraft has active maintenance")

            elif action_type == "assign_crew":
                crew_id = action.get("crew_id")
                crew = conn.execute(
                    "SELECT * FROM Crew WHERE crew_id = ?", (crew_id,)
                ).fetchone()
                checks["crew_exists"] = crew is not None
                checks["crew_available"] = bool(crew and crew["availability"])
                checks["duty_limit"] = bool(
                    crew and float(crew["hours_flown_today"]) < 8.0
                )
                checks["not_already_assigned"] = not bool(
                    conn.execute(
                        "SELECT 1 FROM FlightCrew WHERE flight_id = ? AND crew_id = ?",
                        (flight_id, crew_id),
                    ).fetchone()
                )
                if not checks["crew_exists"]:
                    reasons.append("Crew member not found")
                if not checks["crew_available"]:
                    reasons.append("Crew member unavailable")
                if not checks["duty_limit"]:
                    reasons.append("Crew member reached the 8-hour duty limit")
                if not checks["not_already_assigned"]:
                    reasons.append("Crew member already assigned to this flight")

            elif action_type == "reschedule":
                new_departure = action.get("new_departure")
                new_arrival = action.get("new_arrival")
                checks["times_present"] = bool(new_departure and new_arrival)
                checks["departure_before_arrival"] = bool(
                    new_departure and new_arrival and new_departure < new_arrival
                )
                if not checks["times_present"]:
                    reasons.append("Both new departure and arrival are required")
                if not checks["departure_before_arrival"]:
                    reasons.append("Arrival must be after departure")

            elif action_type == "keep":
                # Keeping an open flight is always a valid no-op decision.
                pass

            else:
                reasons.append(f"Unsupported action type: {action_type or 'missing'}")
                checks["supported_action"] = False

            valid = all(checks.values())
            score = 1.0 if valid else sum(checks.values()) / max(1, len(checks))
            return EnvironmentFeedback(valid, round(score, 4), reasons, checks)

    def validate_plan(self, plan: Iterable[dict[str, Any]]) -> EnvironmentFeedback:
        """Validate every step; any invalid operational step invalidates the plan."""
        plan = list(plan)
        if not plan:
            return EnvironmentFeedback(False, 0.0, ["Plan is empty"])

        all_reasons: list[str] = []
        scores: list[float] = []
        checks: dict[str, bool] = {}
        for index, action in enumerate(plan, start=1):
            feedback = self.validate_action(action)
            scores.append(feedback.score)
            checks[f"step_{index}"] = feedback.valid
            if not feedback.valid:
                all_reasons.extend(
                    f"step {index}: {reason}" for reason in feedback.reasons
                )

        return EnvironmentFeedback(
            valid=all(checks.values()),
            score=round(sum(scores) / len(scores), 4),
            reasons=all_reasons,
            checks=checks,
        )
