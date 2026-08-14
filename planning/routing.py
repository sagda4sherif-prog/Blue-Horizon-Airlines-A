"""Route Blue Horizon operational sub-tasks to PS, ToT, or grounded LATS."""

from __future__ import annotations

from .lats import LATSPlanner
from .plan_and_solve import PlanAndSolvePlanner
from .tree_of_thoughts import TreeOfThoughtsPlanner


class PlanningRouter:
    """Choose the cheapest planning method that matches the task shape."""

    def __init__(self, environment):
        self.ps = PlanAndSolvePlanner(environment)
        self.tot = TreeOfThoughtsPlanner(environment)
        self.lats = LATSPlanner(environment)

    @staticmethod
    def choose_strategy(request: str) -> str:
        text = request.lower()
        high_risk = any(
            word in text
            for word in ("allocate", "assign", "backup", "replace", "aircraft", "crew", "cancel")
        )
        branching = any(
            word in text
            for word in ("alternative", "options", "compare", "best", "priority", "which")
        )
        if high_risk:
            return "lats_grounded"
        if branching:
            return "tree_of_thoughts"
        return "plan_and_solve"

    def run(self, request: str) -> dict[str, object]:
        strategy = self.choose_strategy(request)
        if strategy == "lats_grounded":
            result = self.lats.run(request)
        elif strategy == "tree_of_thoughts":
            result = self.tot.run(request)
        else:
            result = self.ps.run(request)
        result["routed_strategy"] = strategy
        return result
