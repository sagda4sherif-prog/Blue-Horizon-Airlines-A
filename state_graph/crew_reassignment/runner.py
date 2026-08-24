from typing import Any

from .graph import build_crew_reassignment_graph
from .nodes import handle_failure
from .state import CrewReassignmentState


def create_initial_state(
    flight_id: int,
    crew_member_id: int,
    reason: str,
    duty_hours_remaining: float,
    candidate_crew: list[dict[str, Any]],
) -> CrewReassignmentState:
    return {
        "flight_id": flight_id,
        "crew_member_id": crew_member_id,
        "reason": reason,
        "duty_hours_remaining": duty_hours_remaining,
        "candidate_crew": candidate_crew,
        "selected_crew_id": None,
        "status": "created",
        "current_node": "start",
        "hitl_required": False,
        "hitl_request_id": None,
        "hitl_decision": None,
        "ticket_id": None,
        "error": None,
    }


def run_crew_reassignment(
    flight_id: int,
    crew_member_id: int,
    reason: str,
    duty_hours_remaining: float,
    candidate_crew: list[dict[str, Any]],
) -> dict[str, Any]:
    graph = build_crew_reassignment_graph()
    state = create_initial_state(
        flight_id, crew_member_id, reason, duty_hours_remaining, candidate_crew
    )

    try:
        result = graph.invoke(state)
    except Exception as error:
        return dict(handle_failure(state, error))

    return dict(result)
