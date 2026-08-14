import time


class EvaluationMetrics:
    def __init__(self):
        self.results = []

    def add_result(
        self,
        scenario_id,
        method,
        success,
        latency_ms,
        trials=1,
        tokens=0,
    ):
        self.results.append({
            "scenario_id": scenario_id,
            "method": method,
            "success": bool(success),
            "latency_ms": latency_ms,
            "trials": trials,
            "tokens": tokens,
        })

    def summary(self):
        if not self.results:
            return {}

        methods = sorted({
            result["method"]
            for result in self.results
        })

        summary = {}

        for method in methods:
            rows = [
                result
                for result in self.results
                if result["method"] == method
            ]

            summary[method] = {
                "success_rate": (
                    sum(r["success"] for r in rows) / len(rows)
                ),
                "average_latency_ms": (
                    sum(r["latency_ms"] for r in rows) / len(rows)
                ),
                "average_trials": (
                    sum(r["trials"] for r in rows) / len(rows)
                ),
                "average_tokens": (
                    sum(r["tokens"] for r in rows) / len(rows)
                ),
            }

        return summary

    def measure(self, function):
        start = time.perf_counter()
        result = function()
        elapsed = (time.perf_counter() - start) * 1000

        return result, elapsed
