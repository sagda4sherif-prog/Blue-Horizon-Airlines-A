# planning_eval/metrics.py
import time
import logging
from typing import Dict, Any, Callable

logger = logging.getLogger("EvaluationMetrics")

class MetricsTracker:
    """
    Tracks operational execution metrics including planning latency, 
    execution latency, total latency, token usage, and trial counts 
    for PS, ToT, and LATS planners.
    """
    def __init__(self):
        self.metrics = {
            "planning_latency_ms": 0.0,
            "execution_latency_ms": 0.0,
            "total_latency_ms": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "trials": 1,
            "success": False
        }

    def measure_execution(self, planner_func: Callable[[], Any], executor_func: Callable[[Any], Any]) -> Dict[str, Any]:
        """Measure planning and execution performance metrics end-to-end."""
        # 1. Measure planning phase latency and token usage
        start_time = time.time()
        plan_result = planner_func()
        planning_time = (time.time() - start_time) * 1000.0

        if isinstance(plan_result, dict):
            self.metrics["input_tokens"] = plan_result.get("input_tokens", 0)
            self.metrics["output_tokens"] = plan_result.get("output_tokens", 0)
            self.metrics["total_tokens"] = self.metrics["input_tokens"] + self.metrics["output_tokens"]

        self.metrics["planning_latency_ms"] = round(planning_time, 2)

        # 2. Measure execution and validation phase latency
        start_exec = time.time()
        exec_result = executor_func(plan_result)
        exec_time = (time.time() - start_exec) * 1000.0

        self.metrics["execution_latency_ms"] = round(exec_time, 2)
        self.metrics["total_latency_ms"] = round(planning_time + exec_time, 2)
        
        if isinstance(exec_result, dict):
            self.metrics["success"] = exec_result.get("valid", exec_result.get("success", False))

        logger.info(f"Metrics Recorded -> Total Latency: {self.metrics['total_latency_ms']}ms, Success: {self.metrics['success']}")
        return self.metrics