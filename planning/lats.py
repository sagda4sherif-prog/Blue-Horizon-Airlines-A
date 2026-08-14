"""Grounded Language Agent Tree Search (LATS) adapter.

The implementation follows the toolkit's compact MCTS shape: select, expand,
evaluate with external feedback, and backpropagate.  The external evaluator
is Blue Horizon's SQLite-backed environment, not a randomized score.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SearchNode:
    action: dict[str, Any] | None
    parent: "SearchNode | None" = None
    children: list["SearchNode"] = field(default_factory=list)
    visits: int = 0
    value: float = 0.0
    valid: bool = False
    reasons: list[str] = field(default_factory=list)

    @property
    def mean_value(self) -> float:
        return self.value / self.visits if self.visits else 0.0

    def ucb(self, exploration: float = 1.0) -> float:
        if self.visits == 0:
            return float("inf")
        parent_visits = max(1, self.parent.visits if self.parent else self.visits)
        return self.mean_value + exploration * math.sqrt(math.log(parent_visits) / self.visits)


class LATSPlanner:
    """Use grounded MCTS-style search for higher-risk operational choices."""

    def __init__(self, environment, iterations: int = 12, exploration: float = 1.0):
        if iterations <= 0:
            raise ValueError("iterations must be greater than 0")
        self.environment = environment
        self.iterations = iterations
        self.exploration = exploration
        self.llm_calls = 0

    def _candidates(self, request: str) -> list[dict[str, Any]]:
        text = request.lower()
        flight_id = self.environment.resolve_flight_id(request, default=1)
        candidates = [{"type": "keep", "flight_id": flight_id}]
        if any(word in text for word in ("aircraft", "maintenance", "mechanical", "backup", "replace")):
            candidates.extend(
                {"type": "assign_aircraft", "flight_id": flight_id, "aircraft_id": aircraft_id}
                for aircraft_id in self.environment.available_aircraft()
            )
            # Include a known risky branch when maintenance data exists.
            snapshot = self.environment.snapshot(flight_id)
            for record in snapshot["maintenance"]:
                candidates.append({
                    "type": "assign_aircraft",
                    "flight_id": flight_id,
                    "aircraft_id": record["aircraft_id"],
                })
        if any(word in text for word in ("crew", "reassign", "backup")):
            candidates.extend(
                {"type": "assign_crew", "flight_id": flight_id, "crew_id": crew_id}
                for crew_id in self.environment.available_crew_for_flight(flight_id)
            )
        return candidates

    def _select(self, root: SearchNode) -> SearchNode:
        node = root
        while node.children:
            unvisited = [child for child in node.children if child.visits == 0]
            if unvisited:
                return unvisited[0]
            node = max(node.children, key=lambda child: child.ucb(self.exploration))
        return node

    def _expand(self, node: SearchNode, candidates: list[dict[str, Any]]) -> list[SearchNode]:
        if node.children:
            return node.children
        for action in candidates:
            node.children.append(SearchNode(action=action, parent=node))
        return node.children

    @staticmethod
    def _relevance(action: dict[str, Any], request: str) -> float:
        text = request.lower()
        kind = action.get("type", "")
        if kind == "assign_aircraft" and any(w in text for w in ("aircraft", "maintenance", "backup", "replace")):
            return 1.0
        if kind == "assign_crew" and any(w in text for w in ("crew", "reassign", "backup")):
            return 1.0
        if kind == "keep":
            return 0.1
        return 0.0

    def _evaluate(self, node: SearchNode, request: str) -> float:
        if node.action is None:
            return 0.0
        feedback = self.environment.validate_action(node.action)
        node.valid = feedback.valid
        node.reasons = list(feedback.reasons)
        # Real environment feedback is the primary score. Relevance is only a
        # tie-breaker between actions that are equally grounded.
        return (2.0 if feedback.valid else 0.0) + feedback.score + self._relevance(node.action, request)

    @staticmethod
    def _backpropagate(node: SearchNode, score: float) -> None:
        current: SearchNode | None = node
        while current is not None:
            current.visits += 1
            current.value += score
            current = current.parent

    def search(self, request: str) -> dict[str, Any]:
        candidates = self._candidates(request)
        root = SearchNode(action=None)
        self._expand(root, candidates)

        for _ in range(self.iterations):
            leaf = self._select(root)
            score = self._evaluate(leaf, request)
            self._backpropagate(leaf, score)

        valid_children = [child for child in root.children if child.valid]
        pool = valid_children or root.children
        best = max(pool, key=lambda child: (child.mean_value, child.visits))
        feedback = self.environment.validate_action(best.action)

        return {
            "strategy": "lats_grounded",
            "request": request,
            "plan": [best.action],
            "feedback": feedback,
            "iterations": self.iterations,
            "visits": {
                str(index): child.visits for index, child in enumerate(root.children)
            },
            "scores": {
                str(index): round(child.mean_value, 4) for index, child in enumerate(root.children)
            },
            "llm_calls": self.llm_calls,
        }

    run = search
