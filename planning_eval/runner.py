# planning_eval/runner.py

import json
import os
import logging
from typing import Any, Callable

from .scenarios import SCENARIOS

logger = logging.getLogger("EvaluationRunner")


class EvaluationRunner:
    """
    Runs planning evaluation scenarios and persists the results.

    Supports:
        EvaluationRunner(planner=..., output_path=...)
        runner.run()

    and the lower-level:
        runner.run_evaluation(scenarios, planner_router)
    """

    def __init__(
        self,
        planner: Callable | None = None,
        output_path: str = "artifacts/planning_results.json",
        results_path: str | None = None,
    ):
        self.planner = planner

        # Keep backward compatibility with the previous results_path API.
        self.output_path = results_path or output_path
        self.results_path = self.output_path

        self._ensure_output_dir()

    def _ensure_output_dir(self):
        """Ensure the output directory exists."""
        directory = os.path.dirname(self.output_path)

        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

    def save_results(self, evaluation_data: dict):
        """Save evaluation results as JSON."""
        with open(
            self.output_path,
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                evaluation_data,
                f,
                indent=4,
                ensure_ascii=False,
            )

        logger.info(
            "Evaluation results saved to %s",
            self.output_path,
        )

    def run(self):
        """
        Run the built-in evaluation scenarios using the supplied planner.

        Returns:
            {
                "scenarios": [...],
                "summary": {...}
            }
        """

        if self.planner is None:
            raise ValueError(
                "A planner must be provided when using EvaluationRunner.run()."
            )

        scenarios = []

        for scenario in SCENARIOS:
            request = scenario.get("request", "")

            try:
                outcome = self.planner(request)

                if not isinstance(outcome, dict):
                    outcome = {
                        "success": bool(outcome),
                        "plan": outcome,
                    }

                success = outcome.get(
                    "success",
                    outcome.get("valid", False),
                )

                scenario_result = {
                    "id": scenario.get("id"),
                    "description": scenario.get("description"),
                    "request": request,
                    "expected_strategy": scenario.get("expected_strategy"),
                    "success": bool(success),
                    "result": outcome,
                }

            except Exception as exc:
                logger.exception(
                    "Scenario failed: %s",
                    scenario.get("id"),
                )

                scenario_result = {
                    "id": scenario.get("id"),
                    "description": scenario.get("description"),
                    "request": request,
                    "expected_strategy": scenario.get("expected_strategy"),
                    "success": False,
                    "error": str(exc),
                }

            scenarios.append(scenario_result)

        passed = sum(
            1
            for scenario in scenarios
            if scenario["success"]
        )

        summary = {
            "total": len(scenarios),
            "passed": passed,
            "failed": len(scenarios) - passed,
        }

        result = {
            "scenarios": scenarios,
            "summary": summary,
        }

        self.save_results(result)

        return result

    def run_evaluation(
        self,
        scenarios: list,
        planner_router,
    ) -> dict:
        """
        Backward-compatible evaluation interface.

        Runs the supplied scenarios through a planner router.
        """

        results = {
            "total_scenarios": len(scenarios),
            "scenarios_passed": 0,
            "details": [],
        }

        for idx, scenario in enumerate(scenarios, start=1):
            logger.info(
                "Running scenario %s: %s",
                idx,
                scenario.get("name", scenario.get("id", "Unnamed")),
            )

            outcome = planner_router.run(
                scenario.get("request", "")
            )

            results["details"].append(
                {
                    "scenario_id": idx,
                    "scenario_name": scenario.get(
                        "name",
                        scenario.get("id"),
                    ),
                    "outcome": outcome,
                }
            )

            if outcome.get("feedback", {}).get("valid", False):
                results["scenarios_passed"] += 1

        self.save_results(results)

        return results