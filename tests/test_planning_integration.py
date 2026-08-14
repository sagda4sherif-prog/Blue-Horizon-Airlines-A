from planning.self_refine import SelfRefiner
from reflexion import ReflexionAgent
from planning_eval.adapter import ProjectAdapter


def test_self_refine_integrates_with_project_adapter():
    def planner(request):
        return {
            "flight_id": request["flight_id"],
            "seat": "premium",
        }

    def validator(plan):
        if plan["seat"] == "premium":
            return {
                "valid": False,
                "errors": ["premium_seat_unavailable"],
            }

        return {
            "valid": True,
            "errors": [],
        }

    adapter = ProjectAdapter(
        planner=planner,
        validator=validator,
    )

    plan = adapter.create_plan({
        "flight_id": "FL-100",
    })

    refiner = SelfRefiner(
        validator=adapter.validate_plan,
        max_iterations=2,
    )

    result = refiner.refine(plan)

    assert result is not None
    assert "plan" in result
    assert "history" in result


def test_reflexion_integrates_with_project_adapter():
    def planner(request, previous_lessons=None):
        if previous_lessons:
            return {
                "flight_id": request["flight_id"],
                "seat": "standard",
            }

        return {
            "flight_id": request["flight_id"],
            "seat": "premium",
        }

    def executor(plan):
        if plan["seat"] == "premium":
            return {
                "success": False,
                "errors": ["premium_seat_unavailable"],
            }

        return {
            "success": True,
            "errors": [],
        }

    adapter = ProjectAdapter(
        planner=planner,
        executor=executor,
    )

    agent = ReflexionAgent(
        planner=adapter.create_plan,
        executor=adapter.execute_plan,
        max_trials=2,
    )

    result = agent.run({
        "flight_id": "FL-100",
    })

    assert result["success"] is True
    assert len(result["trials"]) == 2
    assert len(result["memory"]) == 2
