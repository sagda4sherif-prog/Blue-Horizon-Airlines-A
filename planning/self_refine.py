# planning/self_refine.py
from copy import deepcopy
import logging

logger = logging.getLogger("SelfRefiner")

class SelfRefiner:
    """
    Self-refine planner that iteratively reviews and corrects operational plans
    based on environment feedback, protected by max iteration limits.
    """
    def __init__(self, validator, max_iterations=3):
        self.validator = validator
        self.max_iterations = max_iterations

    def refine(self, plan):
        """Iteratively refine the plan until it passes validation or hits max iterations."""
        current_plan = deepcopy(plan)
        history = []

        for iteration in range(1, self.max_iterations + 1):
            validation = self._validate(current_plan)

            history.append({
                "iteration": iteration,
                "plan": deepcopy(current_plan),
                "validation": deepcopy(validation),
            })

            logger.info(f"Self-Refine Iteration {iteration}: Valid={validation['valid']}")

            if validation["valid"]:
                return {
                    "success": True,
                    "plan": current_plan,
                    "iterations": iteration,
                    "history": history,
                }

            revised_plan = self._revise(
                current_plan,
                validation.get("errors", [])
            )

            if revised_plan == current_plan:
                logger.warning("Self-Refine stalled: No changes made in revised plan.")
                break

            current_plan = revised_plan

        final_validation = self._validate(current_plan)

        return {
            "success": final_validation["valid"],
            "plan": current_plan,
            "iterations": len(history),
            "history": history,
        }

    def _validate(self, plan):
        """Validate the current plan using the provided validator function."""
        result = self.validator(plan)

        if isinstance(result, bool):
            return {
                "valid": result,
                "errors": [] if result else ["Plan validation failed"],
            }

        if not isinstance(result, dict):
            return {
                "valid": bool(result),
                "errors": [] if result else ["Plan validation failed"],
            }

        return {
            "valid": bool(result.get("valid", False)),
            "errors": result.get("reasons", result.get("errors", [])),
        }

    def _revise(self, plan, errors):
        """Revise the plan based on validation errors."""
        revised = deepcopy(plan)

        if isinstance(revised, dict):
            revised.setdefault("corrections", [])
            revised["corrections"].extend(errors)

        elif isinstance(revised, list):
            revised = [
                task for task in revised
                if isinstance(task, dict) and task.get("id") not in errors
            ]

        return revised

def self_refine(plan, validator, max_iterations=3):
    """Helper function to execute self-refining loop."""
    refiner = SelfRefiner(
        validator=validator,
        max_iterations=max_iterations,
    )
    return refiner.refine(plan)