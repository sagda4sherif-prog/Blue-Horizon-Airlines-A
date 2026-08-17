"""Tests for the grounded EnvironmentFeedback source (planning/environment.py).

Run with: pytest tests/test_environment.py -v
These hit the real db/blue_horizon.db fixtures directly with sqlite3 — no
LLM, network, or API key required, unlike the rest of planning/.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from planning.environment import CREW_DUTY_HOUR_LIMIT, GroundedEnvironment, RandomEnvironment

DB_PATH = Path(__file__).resolve().parent.parent / "db" / "blue_horizon.db"


def _env():
    return GroundedEnvironment(db_path=DB_PATH)


def test_available_aircraft_passes():
    # Aircraft 1 (BH-A320) is seeded as Available with no open maintenance.
    feedback = _env().evaluate("Reassign the flight to Aircraft 1.")
    assert feedback.success is True


def test_aircraft_under_high_severity_maintenance_fails():
    # Aircraft 3 has a seeded High-severity 'In Progress' maintenance record.
    feedback = _env().evaluate("Reassign the flight to Aircraft 3.")
    assert feedback.success is False
    assert any("maintenance" in detail.lower() for detail in feedback.details)


def test_available_crew_passes():
    # Crew 1 is available with well under the duty-hour limit.
    feedback = _env().evaluate("Assign backup Crew 1 to cover the delay.")
    assert feedback.success is True


def test_crew_over_duty_limit_fails():
    # Crew 4 is seeded unavailable and at the 8-hour duty ceiling.
    feedback = _env().evaluate("Assign backup Crew 4 to cover the delay.")
    assert feedback.success is False
    assert any(
        "not available" in detail or f"{CREW_DUTY_HOUR_LIMIT}-hour" in detail
        for detail in feedback.details
    )


def test_unverifiable_candidate_is_not_a_free_pass():
    feedback = _env().evaluate("Everything looks fine, ship it.")
    assert feedback.success is False


def test_grounded_catches_what_ungrounded_default_would_miss():
    """The exact contrast the lab asks for: a candidate that reassigns to
    an aircraft mid-High-severity-maintenance is a real operational failure.
    The grounded environment always rejects it; the toolkit's original
    randomized evaluator ignores the candidate text entirely and can pass
    it purely by chance."""
    candidate = "Reassign Flight 3 to Aircraft 3 with backup Crew 4."

    grounded = _env().evaluate(candidate)
    assert grounded.success is False

    import random

    ungrounded_would_have_passed = any(
        RandomEnvironment(rng=random.Random(seed)).evaluate(candidate).success
        for seed in range(50)
    )
    assert ungrounded_would_have_passed, (
        "expected at least one seed where the ungrounded evaluator "
        "incorrectly passes a candidate the grounded evaluator correctly rejects"
    )
