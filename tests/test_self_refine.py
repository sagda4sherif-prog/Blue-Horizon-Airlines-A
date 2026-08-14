from planning.self_refine import SelfRefiner


def test_self_refine_returns_valid_plan():
    calls = {"count": 0}

    def validator(plan):
        calls["count"] += 1

        if calls["count"] == 1:
            return {
                "valid": False,
                "errors": ["invalid_seat"],
            }

        return {
            "valid": True,
            "errors": [],
        }

    refiner = SelfRefiner(
        validator=validator,
        max_iterations=3,
    )

    result = refiner.refine({
        "flight_id": "FL-100",
        "seat": "premium",
    })

    assert result["success"] is True
    assert result["iterations"] >= 1
    assert len(result["history"]) >= 1
