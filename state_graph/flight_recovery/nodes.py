from uuid import uuid4

from ..shared.checkpoint import save_checkpoint
from ..shared.platform_bridge import (
    create_hitl_request,
    create_ticket,
    get_hitl_decision,
)
from .state import GRAPH_NAME, FlightRecoveryState


def checkpoint_state(
    state: FlightRecoveryState,
    node_name: str,
    status: str = "active",
) -> FlightRecoveryState:
    checkpoint_id = save_checkpoint(
        graph_name=GRAPH_NAME,
        run_id=state["run_id"],
        node_name=node_name,
        state=dict(state),
        status=status,
    )
    return {**state, "checkpoint_ref": checkpoint_id, "current_node": node_name}


def initialize_recovery(state: FlightRecoveryState) -> FlightRecoveryState:
    updated: FlightRecoveryState = {
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
    return checkpoint_state(updated, "initialize_recovery")


def analyze_disruption(state: FlightRecoveryState) -> FlightRecoveryState:
    description = state.get(
        "description", "Flight disruption requires operational recovery."
    )
    severity = state.get("severity", "medium")

    plan = [
        "inspect_flight_status",
        "evaluate_aircraft_options",
        "evaluate_crew_options",
        "select_recovery_action",
    ]

    updated: FlightRecoveryState = {
        **state,
        "description": description,
        "severity": severity,
        "plan": plan,
        "status": "analyzing",
        "current_node": "analyze_disruption",
    }
    return checkpoint_state(updated, "analyze_disruption")


def evaluate_recovery(state: FlightRecoveryState) -> FlightRecoveryState:
    severity = state.get("severity", "medium")
    hitl_required = severity == "high"

    updated: FlightRecoveryState = {
        **state,
        "hitl_required": hitl_required,
        "status": "waiting_for_admin" if hitl_required else "ready_for_action",
        "current_node": "evaluate_recovery",
    }
    return checkpoint_state(
        updated, "evaluate_recovery", "waiting_for_hitl" if hitl_required else "active"
    )


def request_admin_approval(state: FlightRecoveryState) -> FlightRecoveryState:
    if not state.get("hitl_required"):
        return state

    hitl_id = create_hitl_request(
        graph_name=GRAPH_NAME,
        run_id=state["run_id"],
        node_name="request_admin_approval",
        reason="high_severity_disruption",
        summary=(
            f"Approve recovery action for flight {state.get('flight_id')} "
            f"({state.get('event_type', 'disruption')}, severity=high)?"
        ),
        checkpoint_state=dict(state),
    )

    updated: FlightRecoveryState = {
        **state,
        "hitl_request_id": hitl_id,
        "status": "waiting_for_admin",
        "current_node": "request_admin_approval",
    }
    return checkpoint_state(updated, "request_admin_approval", "waiting_for_hitl")


def apply_admin_decision(state: FlightRecoveryState) -> FlightRecoveryState:
    hitl_id = state.get("hitl_request_id")
    if hitl_id is None:
        return state

    decision = get_hitl_decision(hitl_id)
    if decision is None:
        return state  # still pending, stay paused

    approved = decision["status"] == "approved"
    updated: FlightRecoveryState = {
        **state,
        "hitl_decision": decision["status"],
        "status": "approved" if approved else "rejected",
        "current_node": "apply_admin_decision",
    }
    return checkpoint_state(
        updated, "apply_admin_decision", "active" if approved else "rejected"
    )


def execute_recovery(state: FlightRecoveryState) -> FlightRecoveryState:
    if state.get("hitl_required") and state.get("status") != "approved":
        return state  # waiting on / rejected by HITL — do not execute

    updated: FlightRecoveryState = {
        **state,
        "selected_action": "operational_recovery",
        "status": "completed",
        "current_node": "execute_recovery",
    }
    return checkpoint_state(updated, "execute_recovery", "completed")


def handle_failure(state: FlightRecoveryState, error: Exception) -> FlightRecoveryState:
    error_message = str(error) or error.__class__.__name__

    ticket_id = create_ticket(
        graph_name=GRAPH_NAME,
        run_id=state.get("run_id"),
        node_name=state.get("current_node"),
        failure_type="GRAPH_EXECUTION_ERROR",
        description=error_message,
        checkpoint_state=dict(state),
    )

    updated: FlightRecoveryState = {
        **state,
        "ticket_id": ticket_id,
        "error": error_message,
        "status": "failed",
        "current_node": "handle_failure",
    }
    return checkpoint_state(updated, "handle_failure", "failed")
