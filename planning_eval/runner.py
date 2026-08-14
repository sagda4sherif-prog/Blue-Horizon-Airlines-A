import json
import os

from .scenarios import SCENARIOS
from .metrics import EvaluationMetrics


class EvaluationRunner:
    def __init__(
        self,
        planner,
        self_refiner=None,
        reflexion_agent=None,
        output_path="artifacts/planning_results.json",
    ):
        self.planner = planner
        self.self_refiner = self_refiner
        self.reflexion_agent = reflexion_agent
        self.output_path = output_path
        self.metrics = EvaluationMetrics()

    def run(self):
        raw_results = []

        for scenario in SCENARIOS:
            request = scenario["request"]

            self._run_method(
                scenario,
                "planner",
                lambda: self.planner(request),
                raw_results,
            )

            if self.self_refiner is not None:
                self._run_method(
                    scenario,
                    "self_refine",
                    lambda: self._run_self_refine(request),
                    raw_results,
                )

            if self.reflexion_agent is not None:
                self._run_method(
                    scenario,
                    "reflexion",
                    lambda: self.reflexion_agent.run(request),
                    raw_results,
                )

        output = {
            "scenarios": raw_results,
            "summary": self.metrics.summary(),
        }

        os.makedirs(
            os.path.dirname(self.output_path),
            exist_ok=True,
        )

        with open(
            self.output_path,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                output,
                file,
                indent=2,
                ensure_ascii=False,
            )

        return output

    def _run_self_refine(self, request):
        plan = self.planner(request)
        return self.self_refiner.refine(plan)

    def _run_method(
        self,
        scenario,
        method,
        function,
        raw_results,
    ):
        result, latency = self.metrics.measure(function)

        success = bool(
            result.get("success", False)
            if isinstance(result, dict)
            else result
        )

        trials = 1

        if isinstance(result, dict):
            trials = result.get(
                "iterations",
                result.get("trials", 1),
            )

        tokens = (
            result.get("tokens", 0)
            if isinstance(result, dict)
            else 0
        )

        self.metrics.add_result(
            scenario_id=scenario["id"],
            method=method,
            success=success,
            latency_ms=latency,
            trials=trials,
            tokens=tokens,
        )

        raw_results.append({
            "scenario_id": scenario["id"],
            "method": method,
            "result": result,
            "latency_ms": latency,
        })
