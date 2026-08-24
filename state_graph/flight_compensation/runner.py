from typing import Any

from .graph import build_flight_compensation_graph
from .nodes import handle_failure
from .state import CompensationState


def create_initial_state(
    flight_id: int,
    passenger_id: int,
    cancellation_reason: str,
) -> CompensationState:
    return {
        "flight_id": flight_id,
        "passenger_id": passenger_id,
        "cancellation_reason": cancellation_reason,
        "compensation_amount": 0.0,
        "policy_context": "",
        "status": "created",
        "current_node": "start",
        "hitl_required": False,
        "hitl_request_id": None,
        "hitl_decision": None,
        "ticket_id": None,
        "error": None,
        "metadata": {},
    }


def run_flight_compensation(
    flight_id: int,
    passenger_id: int,
    cancellation_reason: str,
) -> dict[str, Any]:
    graph = build_flight_compensation_graph()
    state = create_initial_state(flight_id, passenger_id, cancellation_reason)

    try:
        result = graph.invoke(state)
    except Exception as error:
        return dict(handle_failure(state, error))

    return dict(result)
