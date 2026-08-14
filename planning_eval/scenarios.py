SCENARIOS = [
    {
        "id": "cancelled_flight_available_seat",
        "description": "Cancelled flight with an available alternative seat.",
        "request": {
            "flight_id": "FL-100",
            "disruption": "cancelled",
            "requirement": "find an alternative flight with available seats",
        },
    },
    {
        "id": "cancelled_flight_full_alternative",
        "description": "Cancelled flight where the first alternative has no seats.",
        "request": {
            "flight_id": "FL-101",
            "disruption": "cancelled",
            "requirement": "avoid full alternative flights",
        },
    },
    {
        "id": "fallback_after_validation_failure",
        "description": "First alternative fails validation and a fallback is required.",
        "request": {
            "flight_id": "FL-102",
            "disruption": "cancelled",
            "requirement": "select a valid fallback after seat validation failure",
        },
    },
    {
        "id": "constraint_violation",
        "description": "Candidate plan violates an operational constraint.",
        "request": {
            "flight_id": "FL-103",
            "disruption": "cancelled",
            "requirement": "reject plans violating operational constraints",
        },
    },
]
