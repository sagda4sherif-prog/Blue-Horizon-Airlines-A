from uuid import uuid4

from ..shared.checkpoint import save_checkpoint
from ..shared.platform_bridge import (
    create_hitl_request,
    create_ticket,
    get_hitl_decision,
)
from .state import GRAPH_NAME, HITL_THRESHOLD, CompensationState


def checkpoint_state(
    state: CompensationState,
    node_name: str,
    status: str = "active",
) -> CompensationState:
    checkpoint_id = save_checkpoint(
        graph_name=GRAPH_NAME,
        run_id=state["run_id"],
        node_name=node_name,
        state=dict(state),
        status=status,
    )
    return {**state, "checkpoint_ref": checkpoint_id, "current_node": node_name}


def initialize_claim(state: CompensationState) -> CompensationState:
    updated: CompensationState = {
        **state,
        "run_id": state.get("run_id") or str(uuid4()),
        "status": "running",
        "current_node": "initialize_claim",
        "hitl_required": False,
        "hitl_request_id": None,
        "hitl_decision": None,
        "ticket_id": None,
        "error": None,
    }
    return checkpoint_state(updated, "initialize_claim")


def validate_request(state: CompensationState) -> CompensationState:
    if not state.get("flight_id"):
        return handle_failure(state, ValueError("flight_id is required"))
    if not state.get("passenger_id"):
        return handle_failure(state, ValueError("passenger_id is required"))
    if not state.get("cancellation_reason", "").strip():
        return handle_failure(state, ValueError("cancellation_reason is required"))

    updated: CompensationState = {**state, "current_node": "validate_request"}
    return checkpoint_state(updated, "validate_request")


def retrieve_compensation_policy(
    state: CompensationState,
    rag_pipeline=None,
) -> CompensationState:
    if state.get("status") == "failed":
        return state

    if rag_pipeline is not None:
        query = (
            "What is the compensation policy for a cancelled flight "
            f"with reason: {state.get('cancellation_reason')}?"
        )
        policy_context = rag_pipeline.hybrid_search(query, top_k=3)
    else:
        # rag/ isn't required to exercise this graph end-to-end; fall back
        # to a neutral placeholder rather than failing the whole run.
        policy_context = "(no RAG pipeline supplied — using default policy)"

    updated: CompensationState = {
        **state,
        "policy_context": policy_context,
        "current_node": "retrieve_compensation_policy",
    }
    return checkpoint_state(updated, "retrieve_compensation_policy")


def calculate_compensation(state: CompensationState) -> CompensationState:
    if state.get("status") == "failed":
        return state

    # Placeholder tariff — Person 1/3's db/ layer is the real source for
    # fare class, delay length, etc. Swap this out for that lookup.
    amount = 300.0
    hitl_required = amount > HITL_THRESHOLD

    updated: CompensationState = {
        **state,
        "compensation_amount": amount,
        "hitl_required": hitl_required,
        "status": "waiting_for_admin" if hitl_required else "ready_for_action",
        "current_node": "calculate_compensation",
    }
    return checkpoint_state(
        updated,
        "calculate_compensation",
        "waiting_for_hitl" if hitl_required else "active",
    )


def request_hitl_approval(state: CompensationState) -> CompensationState:
    if not state.get("hitl_required"):
        return state

    hitl_id = create_hitl_request(
        graph_name=GRAPH_NAME,
        run_id=state["run_id"],
        node_name="request_hitl_approval",
        reason="compensation_amount_exceeds_threshold",
        summary=(
            f"Approve ${state.get('compensation_amount')} payout for flight "
            f"{state.get('flight_id')} (passenger {state.get('passenger_id')})?"
        ),
        checkpoint_state=dict(state),
    )

    updated: CompensationState = {
        **state,
        "hitl_request_id": hitl_id,
        "status": "waiting_for_admin",
        "current_node": "request_hitl_approval",
    }
    return checkpoint_state(updated, "request_hitl_approval", "waiting_for_hitl")


def apply_decision(state: CompensationState) -> CompensationState:
    if not state.get("hitl_required"):
        updated: CompensationState = {
            **state,
            "status": "approved",
            "current_node": "apply_decision",
        }
        return checkpoint_state(updated, "apply_decision")

    hitl_id = state.get("hitl_request_id")
    if hitl_id is None:
        return state

    decision = get_hitl_decision(hitl_id)
    if decision is None:
        return state  # still pending, stay paused

    approved = decision["status"] == "approved"
    updated = {
        **state,
        "hitl_decision": decision["status"],
        "status": "approved" if approved else "rejected",
        "current_node": "apply_decision",
    }
    return checkpoint_state(updated, "apply_decision", "active" if approved else "rejected")


def issue_payout(state: CompensationState) -> CompensationState:
    if state.get("status") != "approved":
        return state

    updated: CompensationState = {
        **state,
        "status": "completed",
        "current_node": "issue_payout",
    }
    return checkpoint_state(updated, "issue_payout", "completed")


def handle_failure(state: CompensationState, error: Exception) -> CompensationState:
    error_message = str(error) or error.__class__.__name__

    ticket_id = create_ticket(
        graph_name=GRAPH_NAME,
        run_id=state.get("run_id"),
        node_name=state.get("current_node"),
        failure_type="GRAPH_EXECUTION_ERROR",
        description=error_message,
        checkpoint_state=dict(state),
    )

    updated: CompensationState = {
        **state,
        "ticket_id": ticket_id,
        "error": error_message,
        "status": "failed",
        "current_node": "handle_failure",
    }
    return checkpoint_state(updated, "handle_failure", "failed")
