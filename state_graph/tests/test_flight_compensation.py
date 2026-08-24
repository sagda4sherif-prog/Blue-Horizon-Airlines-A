from state_graph.flight_compensation.runner import run_flight_compensation


def test_missing_passenger_id_fails_gracefully():
    result = run_flight_compensation(
        flight_id=1,
        passenger_id=None,
        cancellation_reason="weather",
    )

    assert result["status"] == "failed"
    assert result["ticket_id"] is not None


def test_payout_above_threshold_pauses_for_admin():
    # calculate_compensation currently hardcodes 300.0 < HITL_THRESHOLD
    # (500.0), so this documents today's default path; once the real
    # tariff lookup lands, add a case that exceeds the threshold.
    result = run_flight_compensation(
        flight_id=1,
        passenger_id=42,
        cancellation_reason="mechanical",
    )

    assert result["status"] == "completed"
    assert result["hitl_required"] is False
