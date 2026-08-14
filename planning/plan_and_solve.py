"""Plan-and-Solve adapter for Blue Horizon Airlines.

Adapted from the reference toolkit's two-phase interface: first create one
explicit plan, then validate/solve that plan against the grounded airline
environment.  A model callable can be injected later without changing the
planner API.
"""

from __future__ import annotations

from typing import Any, Callable


class PlanAndSolvePlanner:
    """Single-pass planner for deterministic or low-branching tasks."""

    def __init__(self, environment, model: Callable[[str], Any] | None = None):
        self.environment = environment
        self.model = model
        self.llm_calls = 0

    def _fallback_plan(self, request: str) -> list[dict[str, Any]]:
        text = request.lower()
        flight_id = self.environment.resolve_flight_id(request, default=1)

        if "crew" in text and any(word in text for word in ("backup", "reassign", "assign")):
            candidates = self.environment.available_crew_for_flight(flight_id)
            if candidates:
                return [{"type": "assign_crew", "flight_id": flight_id, "crew_id": candidates[0]}]

        if "aircraft" in text and any(word in text for word in ("backup", "replace", "assign")):
            candidates = self.environment.available_aircraft()
            if candidates:
                return [{"type": "assign_aircraft", "flight_id": flight_id, "aircraft_id": candidates[0]}]

        if "reschedule" in text or "delay" in text:
            snapshot = self.environment.snapshot(flight_id)
            departure = str(snapshot["flight"]["departure_time"])
            arrival = str(snapshot["flight"]["arrival_time"])
            # Keep a deterministic valid ordering for the local demo.
            return [{
                "type": "reschedule",
                "flight_id": flight_id,
                "new_departure": departure,
                "new_arrival": arrival,
            }]

        return [{"type": "keep", "flight_id": flight_id}]

    def plan(self, request: str) -> list[dict[str, Any]]:
        if not isinstance(request, str) or not request.strip():
            raise ValueError("request must be a non-empty string")
        if self.model is not None:
            self.llm_calls += 1
            result = self.model(request)
            if not isinstance(result, list) or not all(isinstance(x, dict) for x in result):
                raise ValueError("model must return a list of action dictionaries")
            return result
        return self._fallback_plan(request)

    def solve(self, request: str) -> dict[str, Any]:
        plan = self.plan(request)
        feedback = self.environment.validate_plan(plan)
        return {
            "strategy": "plan_and_solve",
            "request": request,
            "plan": plan,
            "feedback": feedback,
            "llm_calls": self.llm_calls,
        }

    run = solve
