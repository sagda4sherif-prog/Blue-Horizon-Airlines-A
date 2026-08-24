from typing import Any

from .graph import build_flight_recovery_graph
from .nodes import handle_failure
from .state import FlightRecoveryState


def create_initial_state(
    flight_id: int,
    event_type: str,
    severity: str,
    description: str,
) -> FlightRecoveryState:
    return {
        "flight_id": flight_id,
        "event_type": event_type,
        "severity": severity,
        "description": description,
        "status": "created",
        "current_node": "start",
        "hitl_required": False,
        "hitl_request_id": None,
        "hitl_decision": None,
        "ticket_id": None,
        "error": None,
        "plan": [],
    }


def run_flight_recovery(
    flight_id: int,
    event_type: str,
    severity: str,
    description: str,
) -> dict[str, Any]:
    graph = build_flight_recovery_graph()
    state = create_initial_state(flight_id, event_type, severity, description)

    try:
        result = graph.invoke(state)
    except Exception as error:
        return dict(handle_failure(state, error))

    return dict(result)
