from typing import Any, TypedDict

GRAPH_NAME = "crew_reassignment"

# Crew members within this many hours of their duty limit can be
# reassigned automatically; closer than that requires an admin to sign
# off — this is the exact liability the README calls out ("nothing would
# stop it from assigning a crew member already past their duty limit").
DUTY_HOUR_SAFETY_MARGIN = 2.0


class CrewReassignmentState(TypedDict, total=False):
    run_id: str
    flight_id: int
    crew_member_id: int
    reason: str

    duty_hours_remaining: float
    candidate_crew: list[dict[str, Any]]
    selected_crew_id: int | None

    status: str
    current_node: str

    hitl_required: bool
    hitl_request_id: int | None
    hitl_decision: str | None

    ticket_id: int | None
    error: str | None

    checkpoint_ref: str | None
