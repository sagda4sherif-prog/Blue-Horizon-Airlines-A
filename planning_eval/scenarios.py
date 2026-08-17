# planning_eval/scenarios.py
"""Evaluation scenarios for Blue Horizon Airlines operational disruptions.

Defines structured scenarios for testing dynamic DAGs, fallback routing,
and grounded environment validation against the live SQLite database.
"""

from __future__ import annotations
from typing import Any, Dict, List

SCENARIOS: List[Dict[str, Any]] = [
    {
        "id": "cancelled_flight_available_seat",
        "description": "Cancelled flight with an available alternative seat or routing.",
        "request": "Flight BH218 is cancelled, find an alternative flight or available resources.",
        "expected_strategy": "plan_and_solve"
    },
    {
        "id": "cancelled_flight_full_alternative",
        "description": "Cancelled flight where premium seats are full, requiring dynamic rerouting.",
        "request": "Premium cabin is fully booked for flight BH305. Avoid full alternatives and use fallback.",
        "expected_strategy": "tree_of_thoughts"
    },
    {
        "id": "fallback_after_validation_failure",
        "description": "First alternative fails validation and a dynamic fallback is required.",
        "request": "Flight BH204 crew reached duty limit; select a valid fallback after validation failure.",
        "expected_strategy": "lats_grounded"
    },
    {
        "id": "constraint_violation",
        "description": "Candidate plan violates an operational constraint (e.g., active maintenance).",
        "request": "Allocate an aircraft for flight BH218, rejecting plans violating maintenance constraints.",
        "expected_strategy": "lats_grounded"
    },
]