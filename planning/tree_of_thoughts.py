"""Tree-of-Thoughts planning adapted to Blue Horizon operations.

The reference toolkit's generate/evaluate/beam-search shape is preserved, but
candidate actions are evaluated by the real airline database instead of an
LLM-only self-score.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ThoughtNode:
    action: dict[str, Any]
    score: float
    feedback: Any


class TreeOfThoughtsPlanner:
    """Generate several candidate actions, evaluate them, and keep the best."""

    def __init__(self, environment, beam_width: int = 3):
        if beam_width <= 0:
            raise ValueError("beam_width must be greater than 0")
        self.environment = environment
        self.beam_width = beam_width
        self.llm_calls = 0

    def generate_thoughts(self, request: str) -> list[dict[str, Any]]:
        text = request.lower()
        flight_id = self.environment.resolve_flight_id(request, default=1)
        candidates: list[dict[str, Any]] = [{"type": "keep", "flight_id": flight_id}]

        if any(word in text for word in ("aircraft", "mechanical", "maintenance", "backup", "replace")):
            # Include an invalid maintenance branch deliberately so grounded
            # evaluation can prune it when the database says it is unsafe.
            snapshot = self.environment.snapshot(flight_id)
            maintenance_ids = {m["aircraft_id"] for m in snapshot["maintenance"]}
            aircraft_ids = [a["aircraft_id"] for a in snapshot["aircraft"]]
            for aircraft_id in aircraft_ids:
                if aircraft_id in maintenance_ids or aircraft_id in self.environment.available_aircraft():
                    candidates.append({
                        "type": "assign_aircraft",
                        "flight_id": flight_id,
                        "aircraft_id": aircraft_id,
                    })

        if any(word in text for word in ("crew", "reassign", "backup")):
            # Add several alternatives for the branching case.
            for crew_id in self.environment.available_crew_for_flight(flight_id):
                candidates.append({
                    "type": "assign_crew",
                    "flight_id": flight_id,
                    "crew_id": crew_id,
                })

        return candidates

    @staticmethod
    def _relevance(action: dict[str, Any], request: str) -> float:
        text = request.lower()
        kind = action.get("type", "")
        if kind == "assign_aircraft" and any(w in text for w in ("aircraft", "maintenance", "backup", "replace")):
            return 1.0
        if kind == "assign_crew" and any(w in text for w in ("crew", "reassign", "backup")):
            return 1.0
        if kind == "keep" and not any(w in text for w in ("aircraft", "crew", "reschedule", "delay")):
            return 0.2
        return 0.0

    def search(self, request: str) -> dict[str, Any]:
        nodes: list[ThoughtNode] = []
        for action in self.generate_thoughts(request):
            feedback = self.environment.validate_action(action)
            # Grounding dominates selection: invalid actions are never preferred
            # over a valid action simply because the wording looks relevant.
            score = (2.0 if feedback.valid else 0.0) + feedback.score + self._relevance(action, request)
            nodes.append(ThoughtNode(action, score, feedback))

        nodes.sort(key=lambda node: (node.feedback.valid, node.score), reverse=True)
        selected = nodes[: self.beam_width]
        best = selected[0]
        return {
            "strategy": "tree_of_thoughts",
            "request": request,
            "plan": [best.action],
            "feedback": best.feedback,
            "candidate_count": len(nodes),
            "explored": [
                {"action": node.action, "score": round(node.score, 4), "valid": node.feedback.valid}
                for node in selected
            ],
            "llm_calls": self.llm_calls,
        }

    run = search
