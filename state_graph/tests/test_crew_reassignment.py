from state_graph.crew_reassignment.runner import run_crew_reassignment

CANDIDATE = [{"crew_id": 99, "name": "J. Rivera"}]


def test_ample_duty_hours_completes_without_hitl():
    result = run_crew_reassignment(
        flight_id=1,
        crew_member_id=7,
        reason="crew_illness",
        duty_hours_remaining=6.0,
        candidate_crew=CANDIDATE,
    )

    assert result["status"] == "completed"
    assert result["selected_crew_id"] == 99
    assert result["hitl_required"] is False


def test_low_duty_hours_pauses_for_admin():
    result = run_crew_reassignment(
        flight_id=1,
        crew_member_id=7,
        reason="crew_illness",
        duty_hours_remaining=1.5,
        candidate_crew=CANDIDATE,
    )

    assert result["status"] == "waiting_for_admin"
    assert result["hitl_required"] is True
    assert result["hitl_request_id"] is not None


def test_no_candidate_crew_fails_gracefully():
    result = run_crew_reassignment(
        flight_id=1,
        crew_member_id=7,
        reason="crew_illness",
        duty_hours_remaining=6.0,
        candidate_crew=[],
    )

    assert result["status"] == "failed"
    assert result["ticket_id"] is not None
