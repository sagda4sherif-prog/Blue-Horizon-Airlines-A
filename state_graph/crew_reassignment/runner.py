from typing import Any

from .graph import build_crew_reassignment_graph
from .nodes import handle_failure
from .state import CrewReassignmentState


def create_initial_state(
    flight_id: int,
    crew_member_id: int,
    reason: str,
    duty_hours_remaining: float | None = None,
    candidate_crew: list[dict[str, Any]] | None = None,
) -> CrewReassignmentState:
    return {
        "flight_id": flight_id,
        "crew_member_id": crew_member_id,
        "reason": reason,

        "duty_hours_remaining": (
            duty_hours_remaining
            if duty_hours_remaining is not None
            else 0.0
        ),

        "candidate_crew": (
            candidate_crew
            if candidate_crew is not None
            else []
        ),

        "selected_crew_id": None,

        "status": "created",
        "current_node": "start",

        "hitl_required": False,
        "hitl_request_id": None,
        "hitl_decision": None,

        "ticket_id": None,
        "error": None,
        "checkpoint_ref": None,
    }


def run_crew_reassignment(
    flight_id: int,
    crew_member_id: int,
    reason: str,
    duty_hours_remaining: float | None = None,
    candidate_crew: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:

    graph = build_crew_reassignment_graph()

    state = create_initial_state(
        flight_id=flight_id,
        crew_member_id=crew_member_id,
        reason=reason,
        duty_hours_remaining=duty_hours_remaining,
        candidate_crew=candidate_crew,
    )

    try:
        result = graph.invoke(state)
    except Exception as error:
        return dict(handle_failure(state, error))

    return dict(result)
