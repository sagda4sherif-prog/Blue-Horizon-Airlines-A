# planning/self_refine.py
from copy import deepcopy
import logging

logger = logging.getLogger("SelfRefiner")

class SelfRefiner:
    """
    Self-refine planner that iteratively reviews and corrects operational plans
    based on environment feedback, protected by max iteration limits.
    """
    def __init__(self, validator, max_iterations=3, reviser=None):
        self.validator = validator
        self.max_iterations = max_iterations
        # Bug fix (see README Bug Fix Log): the built-in `_revise` below
        # only ever mutates dict- or list-shaped plans; a string plan (the
        # common shape for "cheap to redo" text output, e.g. a drafted
        # notification) fell through to a bare `deepcopy(plan)` with no
        # actual edit, so the loop always stalled after one iteration
        # regardless of `max_iterations`. `reviser(plan, errors) -> plan`
        # lets a caller supply a real revision step for any plan shape;
        # when omitted, behavior for dict/list plans is unchanged.
        self.reviser = reviser

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
        if self.reviser is not None:
            return self.reviser(deepcopy(plan), errors)

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