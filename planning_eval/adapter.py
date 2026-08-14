class ProjectAdapter:
    def __init__(self, planner, validator=None, executor=None):
        self.planner = planner
        self.validator = validator
        self.executor = executor

    def create_plan(self, request, previous_lessons=None):
        try:
            return self.planner(
                request=request,
                previous_lessons=previous_lessons or [],
            )
        except TypeError:
            try:
                return self.planner(request)
            except TypeError:
                return self.planner()

    def validate_plan(self, plan):
        if self.validator is None:
            return {
                "valid": True,
                "errors": [],
            }

        result = self.validator(plan)

        if isinstance(result, bool):
            return {
                "valid": result,
                "errors": [] if result else ["Validation failed"],
            }

        if isinstance(result, dict):
            return {
                "valid": bool(result.get("valid", False)),
                "errors": result.get("errors", []),
            }

        return {
            "valid": bool(result),
            "errors": [] if result else ["Validation failed"],
        }

    def execute_plan(self, plan):
        if self.executor is None:
            validation = self.validate_plan(plan)

            return {
                "success": validation["valid"],
                "errors": validation["errors"],
            }

        result = self.executor(plan)

        if isinstance(result, bool):
            return {
                "success": result,
                "errors": [] if result else ["Execution failed"],
            }

        if isinstance(result, dict):
            return result

        return {
            "success": bool(result),
            "errors": [] if result else ["Execution failed"],
        }
