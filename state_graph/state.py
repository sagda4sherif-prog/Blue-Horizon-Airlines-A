from typing import Any, TypedDict


class FlightRecoveryState(TypedDict, total=False):
    run_id: str
    flight_id: int

    event_type: str
    severity: str
    description: str

    flight: dict[str, Any]
    aircraft_options: list[dict[str, Any]]
    crew_options: list[dict[str, Any]]

    plan: list[str]
    selected_action: str

    status: str
    current_node: str

    hitl_required: bool
    hitl_request_id: str | None
    hitl_decision: str | None

    ticket_id: str | None
    error: str | None

    checkpoint_ref: str | None
