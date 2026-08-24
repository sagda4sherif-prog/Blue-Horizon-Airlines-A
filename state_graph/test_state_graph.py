from state_graph.runner import run_flight_recovery


def test_low_severity_recovery():
    result = run_flight_recovery(
        flight_id=1,
        event_type="delay",
        severity="low",
        description="Minor operational delay",
    )

    assert result["status"] == "completed"
    assert result["current_node"] == "execute_recovery"


def test_high_severity_requires_hitl():
    result = run_flight_recovery(
        flight_id=1,
        event_type="cancellation",
        severity="high",
        description="Major operational disruption",
    )

    assert result["status"] == "waiting_for_admin"
    assert result["hitl_required"] is True
    assert result["hitl_request_id"] is not None
