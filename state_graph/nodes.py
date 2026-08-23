from uuid import uuid4

from .checkpoint import save_checkpoint
from .hitl import create_hitl_request
from .state import FlightRecoveryState
from .tickets import create_ticket


def checkpoint_state(
    state: FlightRecoveryState,
    node_name: str,
    status: str = "active",
) -> FlightRecoveryState:
    checkpoint_id = save_checkpoint(
        run_id=state["run_id"],
        node_name=node_name,
        state=dict(state),
        status=status,
    )

    return {
        **state,
        "checkpoint_id": str(checkpoint_id),
        "current_node": node_name,
    }


def initialize_recovery(
    state: FlightRecoveryState,
) -> FlightRecoveryState:
    updated_state: FlightRecoveryState = {
        **state,
        "run_id": state.get("run_id") or str(uuid4()),
        "status": "running",
        "current_node": "initialize_recovery",
        "hitl_required": False,
        "hitl_request_id": None,
        "hitl_decision": None,
        "ticket_id": None,
        "error": None,
    }

    return checkpoint_state(
        updated_state,
        "initialize_recovery",
    )


def analyze_disruption(
    state: FlightRecoveryState,
) -> FlightRecoveryState:
    description = state.get(
        "description",
        "Flight disruption requires operational recovery.",
    )

    severity = state.get("severity", "medium")

    plan = [
        "inspect_flight_status",
        "evaluate_aircraft_options",
        "evaluate_crew_options",
        "select_recovery_action",
    ]

    updated_state: FlightRecoveryState = {
        **state,
        "description": description,
        "severity": severity,
        "plan": plan,
        "status": "analyzing",
        "current_node": "analyze_disruption",
    }

    return checkpoint_state(
        updated_state,
        "analyze_disruption",
    )


def evaluate_recovery(
    state: FlightRecoveryState,
) -> FlightRecoveryState:
    severity = state.get("severity", "medium")

    if severity == "high":
        updated_state: FlightRecoveryState = {
            **state,
            "hitl_required": True,
            "status": "waiting_for_admin",
            "current_node": "evaluate_recovery",
        }

        return checkpoint_state(
            updated_state,
            "evaluate_recovery",
            "waiting_for_hitl",
        )

    updated_state: FlightRecoveryState = {
        **state,
        "hitl_required": False,
        "status": "ready_for_action",
        "current_node": "evaluate_recovery",
    }

    return checkpoint_state(
        updated_state,
        "evaluate_recovery",
    )


def request_admin_approval(
    state: FlightRecoveryState,
) -> FlightRecoveryState:
    if not state.get("hitl_required"):
        return state

    request_id = create_hitl_request(
        state=state,
        node_name="request_admin_approval",
        reason=(
            "High-severity flight disruption requires "
            "administrative approval before recovery."
        ),
    )

    updated_state: FlightRecoveryState = {
        **state,
        "hitl_request_id": request_id,
        "status": "waiting_for_admin",
        "current_node": "request_admin_approval",
    }

    return checkpoint_state(
        updated_state,
        "request_admin_approval",
        "waiting_for_hitl",
    )


def apply_admin_decision(
    state: FlightRecoveryState,
) -> FlightRecoveryState:
    decision = state.get("hitl_decision")

    if decision is None:
        return state

    if decision.lower() not in {"approve", "approved"}:
        updated_state: FlightRecoveryState = {
            **state,
            "status": "rejected",
            "current_node": "apply_admin_decision",
        }

        return checkpoint_state(
            updated_state,
            "apply_admin_decision",
            "rejected",
        )

    updated_state: FlightRecoveryState = {
        **state,
        "status": "approved",
        "current_node": "apply_admin_decision",
    }

    return checkpoint_state(
        updated_state,
        "apply_admin_decision",
    )


def execute_recovery(
    state: FlightRecoveryState,
) -> FlightRecoveryState:
    if state.get("hitl_required") and state.get("hitl_decision") is None:
        return state

    if state.get("hitl_required"):
        decision = state.get("hitl_decision", "").lower()

        if decision not in {"approve", "approved"}:
            return state

    updated_state: FlightRecoveryState = {
        **state,
        "selected_action": "operational_recovery",
        "status": "completed",
        "current_node": "execute_recovery",
    }

    return checkpoint_state(
        updated_state,
        "execute_recovery",
        "completed",
    )


def handle_failure(
    state: FlightRecoveryState,
    error: Exception,
) -> FlightRecoveryState:
    error_message = str(error) or error.__class__.__name__

    ticket_id = create_ticket(
        state=state,
        node_name=state.get("current_node", "unknown"),
        error=error_message,
    )

    updated_state: FlightRecoveryState = {
        **state,
        "ticket_id": ticket_id,
        "error": error_message,
        "status": "failed",
        "current_node": "handle_failure",
    }

    return checkpoint_state(
        updated_state,
        "handle_failure",
        "failed",
    )
