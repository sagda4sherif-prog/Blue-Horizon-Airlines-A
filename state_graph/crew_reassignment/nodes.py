from uuid import uuid4

from ..shared.checkpoint import save_checkpoint
from ..shared.platform_bridge import (
    create_hitl_request,
    create_ticket,
    get_hitl_decision,
)
from .state import DUTY_HOUR_SAFETY_MARGIN, GRAPH_NAME, CrewReassignmentState


def checkpoint_state(
    state: CrewReassignmentState,
    node_name: str,
    status: str = "active",
) -> CrewReassignmentState:
    checkpoint_id = save_checkpoint(
        graph_name=GRAPH_NAME,
        run_id=state["run_id"],
        node_name=node_name,
        state=dict(state),
        status=status,
    )
    return {**state, "checkpoint_ref": checkpoint_id, "current_node": node_name}


def initialize_reassignment(state: CrewReassignmentState) -> CrewReassignmentState:
    updated: CrewReassignmentState = {
        **state,
        "run_id": state.get("run_id") or str(uuid4()),
        "status": "running",
        "current_node": "initialize_reassignment",
        "hitl_required": False,
        "hitl_request_id": None,
        "hitl_decision": None,
        "ticket_id": None,
        "error": None,
    }
    return checkpoint_state(updated, "initialize_reassignment")


def analyze_crew_duty(state: CrewReassignmentState) -> CrewReassignmentState:
    """
    Person 1's db/ layer (Crew, CrewAssignments) is the real source for
    duty_hours_remaining and candidate_crew; this node assumes they're
    already on the incoming state (or defaults defensively if not).
    """
    duty_hours_remaining = state.get("duty_hours_remaining", 0.0)
    candidate_crew = state.get("candidate_crew", [])

    if not candidate_crew:
        return handle_failure(
            state, ValueError("no candidate crew available for reassignment")
        )

    updated: CrewReassignmentState = {
        **state,
        "duty_hours_remaining": duty_hours_remaining,
        "candidate_crew": candidate_crew,
        "status": "analyzing",
        "current_node": "analyze_crew_duty",
    }
    return checkpoint_state(updated, "analyze_crew_duty")


def evaluate_reassignment(state: CrewReassignmentState) -> CrewReassignmentState:
    duty_hours_remaining = state.get("duty_hours_remaining", 0.0)
    hitl_required = duty_hours_remaining <= DUTY_HOUR_SAFETY_MARGIN

    updated: CrewReassignmentState = {
        **state,
        "hitl_required": hitl_required,
        "status": "waiting_for_admin" if hitl_required else "ready_for_action",
        "current_node": "evaluate_reassignment",
    }
    return checkpoint_state(
        updated,
        "evaluate_reassignment",
        "waiting_for_hitl" if hitl_required else "active",
    )


def request_admin_approval(state: CrewReassignmentState) -> CrewReassignmentState:
    if not state.get("hitl_required"):
        return state

    hitl_id = create_hitl_request(
        graph_name=GRAPH_NAME,
        run_id=state["run_id"],
        node_name="request_admin_approval",
        reason="crew_duty_hours_below_safety_margin",
        summary=(
            f"Approve reassigning crew for flight {state.get('flight_id')} "
            f"(crew member {state.get('crew_member_id')} has "
            f"{state.get('duty_hours_remaining')}h duty time remaining)?"
        ),
        checkpoint_state=dict(state),
    )

    updated: CrewReassignmentState = {
        **state,
        "hitl_request_id": hitl_id,
        "status": "waiting_for_admin",
        "current_node": "request_admin_approval",
    }
    return checkpoint_state(updated, "request_admin_approval", "waiting_for_hitl")


def apply_admin_decision(state: CrewReassignmentState) -> CrewReassignmentState:
    hitl_id = state.get("hitl_request_id")
    if hitl_id is None:
        return state

    decision = get_hitl_decision(hitl_id)
    if decision is None:
        return state  # still pending, stay paused

    approved = decision["status"] == "approved"
    updated: CrewReassignmentState = {
        **state,
        "hitl_decision": decision["status"],
        "status": "approved" if approved else "rejected",
        "current_node": "apply_admin_decision",
    }
    return checkpoint_state(
        updated, "apply_admin_decision", "active" if approved else "rejected"
    )


def execute_reassignment(state: CrewReassignmentState) -> CrewReassignmentState:
    if state.get("hitl_required") and state.get("status") != "approved":
        return state

    candidate_crew = state.get("candidate_crew", [])
    selected = candidate_crew[0] if candidate_crew else None

    updated: CrewReassignmentState = {
        **state,
        "selected_crew_id": selected["crew_id"] if selected else None,
        "status": "completed",
        "current_node": "execute_reassignment",
    }
    return checkpoint_state(updated, "execute_reassignment", "completed")


def handle_failure(
    state: CrewReassignmentState, error: Exception
) -> CrewReassignmentState:
    error_message = str(error) or error.__class__.__name__

    ticket_id = create_ticket(
        graph_name=GRAPH_NAME,
        run_id=state.get("run_id"),
        node_name=state.get("current_node"),
        failure_type="GRAPH_EXECUTION_ERROR",
        description=error_message,
        checkpoint_state=dict(state),
    )

    updated: CrewReassignmentState = {
        **state,
        "ticket_id": ticket_id,
        "error": error_message,
        "status": "failed",
        "current_node": "handle_failure",
    }
    return checkpoint_state(updated, "handle_failure", "failed")
