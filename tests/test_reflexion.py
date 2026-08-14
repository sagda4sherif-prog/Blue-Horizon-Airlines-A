from reflexion import ReflexionAgent


def test_reflexion_learns_from_failed_trial():
    calls = {"count": 0}

    def planner(request, previous_lessons):
        calls["count"] += 1

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

    agent = ReflexionAgent(
        planner=planner,
        executor=executor,
        max_trials=3,
    )

    result = agent.run({
        "flight_id": "FL-100",
    })

    assert result["success"] is True
    assert len(result["trials"]) == 2
    assert len(result["memory"]) == 2
