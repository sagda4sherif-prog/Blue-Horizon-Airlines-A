# planning_eval/runner.py
import json
import os
import logging

logger = logging.getLogger("EvaluationRunner")

class EvaluationRunner:
    """
    Runs planning evaluation scenarios, collects performance metrics, 
    and saves results directly to artifacts/planning_results.json.
    """
    def __init__(self, results_path: str = "artifacts/planning_results.json"):
        self.results_path = results_path
        self._ensure_artifacts_dir()

    def _ensure_artifacts_dir(self):
        """Ensure the artifacts directory exists."""
        directory = os.path.dirname(self.results_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

    def save_results(self, evaluation_data: dict):
        """Save planning and evaluation results to the JSON artifact file."""
        try:
            with open(self.results_path, "w", encoding="utf-8") as f:
                json.dump(evaluation_data, f, indent=4, ensure_ascii=False)
            logger.info(f"Evaluation results successfully saved to {self.results_path}")
        except Exception as e:
            logger.error(f"Failed to save evaluation results: {e}")

    def run_evaluation(self, scenarios: list, planner_router) -> dict:
        """Run evaluation across scenarios and persist results."""
        results = {
            "total_scenarios": len(scenarios),
            "scenarios_passed": 0,
            "details": []
        }

        for idx, scenario in enumerate(scenarios, start=1):
            logger.info(f"Running scenario {idx}: {scenario.get('name', 'Unnamed')}")
            # Execute planning and routing logic
            outcome = planner_router.run(scenario.get("request", ""))
            
            results["details"].append({
                "scenario_id": idx,
                "scenario_name": scenario.get("name"),
                "outcome": outcome
            })
            
            if outcome.get("feedback", {}).get("valid", False):
                results["scenarios_passed"] += 1

        # Persist results to artifacts/planning_results.json
        self.save_results(results)
        return results