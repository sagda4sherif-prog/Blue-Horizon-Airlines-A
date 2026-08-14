from copy import deepcopy


class SelfRefiner:
    def __init__(self, validator, max_iterations=3):
        self.validator = validator
        self.max_iterations = max_iterations

    def refine(self, plan):
        current_plan = deepcopy(plan)
        history = []

        for iteration in range(1, self.max_iterations + 1):
            validation = self._validate(current_plan)

            history.append({
                "iteration": iteration,
                "plan": deepcopy(current_plan),
                "validation": deepcopy(validation),
            })

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
            "errors": result.get("errors", []),
        }

    def _revise(self, plan, errors):
        revised = deepcopy(plan)

        if isinstance(revised, dict):
            revised.setdefault("corrections", [])
            revised["corrections"].extend(errors)

        elif isinstance(revised, list):
            revised = [
                task for task in revised
                if task.get("id") not in errors
                if isinstance(task, dict)
            ]

        return revised


def self_refine(plan, validator, max_iterations=3):
    refiner = SelfRefiner(
        validator=validator,
        max_iterations=max_iterations,
    )
    return refiner.refine(plan)
