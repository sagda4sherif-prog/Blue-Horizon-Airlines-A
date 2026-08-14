from copy import deepcopy


class SelfRefiner:
    def __init__(self, validator=None, max_iterations=3):
        self.validator = validator
        self.max_iterations = max_iterations

    def refine(self, plan):
        current_plan = deepcopy(plan)
        history = []

        for iteration in range(self.max_iterations):
            feedback = self._validate(current_plan)

            history.append(
                {
                    "iteration": iteration + 1,
                    "plan": deepcopy(current_plan),
                    "feedback": feedback,
                }
            )

            if feedback["valid"]:
                return {
                    "plan": current_plan,
                    "valid": True,
                    "iterations": iteration + 1,
                    "history": history,
                }

            revised_plan = self._revise(current_plan, feedback)

            if revised_plan == current_plan:
                return {
                    "plan": current_plan,
                    "valid": False,
                    "iterations": iteration + 1,
                    "history": history,
                }

            current_plan = revised_plan

        final_feedback = self._validate(current_plan)

        return {
            "plan": current_plan,
            "valid": final_feedback["valid"],
            "iterations": self.max_iterations,
            "history": history,
        }

    def _validate(self, plan):
        if self.validator is None:
            return {
                "valid": True,
                "errors": [],
            }

        result = self.validator(plan)

        if isinstance(result, bool):
            return {
                "valid": result,
                "errors": [] if result else ["Plan validation failed"],
            }

        if isinstance(result, dict):
            return {
                "valid": result.get("valid", False),
                "errors": result.get("errors", []),
            }

        return {
            "valid": bool(result),
            "errors": [] if result else ["Plan validation failed"],
        }

    def _revise(self, plan, feedback):
        revised_plan = deepcopy(plan)
        errors = feedback.get("errors", [])

        if isinstance(revised_plan, dict):
            revised_plan["validation_errors"] = errors

        elif isinstance(revised_plan, list):
            revised_plan = [
                task
                for task in revised_plan
                if task not in errors
            ]

        return revised_plan


def self_refine(plan, validator=None, max_iterations=3):
    refiner = SelfRefiner(
        validator=validator,
        max_iterations=max_iterations,
    )
    return refiner.refine(plan)
