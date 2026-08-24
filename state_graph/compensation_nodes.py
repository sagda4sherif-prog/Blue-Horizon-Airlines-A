from __future__ import annotations

from state_graph.compensation_state import CompensationState


HITL_THRESHOLD = 500.0


def validate_request(state: CompensationState) -> CompensationState:
    state.current_node = "validate_request"

    if state.flight_id is None:
        state.fail("flight_id is required")
        return state

    if state.passenger_id is None:
        state.fail("passenger_id is required")
        return state

    state.mark_completed("validate_request")
    return state


def calculate_compensation(state: CompensationState) -> CompensationState:
    state.current_node = "calculate_compensation"

    if state.status == "failed":
        return state

    if state.cancellation_reason.strip() == "":
        state.fail("cancellation_reason is required")
        return state

    state.compensation_amount = 300.0

    if state.compensation_amount > HITL_THRESHOLD:
        state.requires_hitl = True

    state.mark_completed("calculate_compensation")
    return state


def retrieve_compensation_policy(
    state: CompensationState,
    rag_pipeline=None,
) -> CompensationState:
    state.current_node = "retrieve_compensation_policy"

    if state.status == "failed":
        return state

    if rag_pipeline is None:
        state.fail("RAG pipeline is required")
        return state

    query = (
        "What is the compensation policy for a cancelled flight "
        f"with reason: {state.cancellation_reason}?"
    )

    state.policy_context = rag_pipeline.hybrid_search(
        query,
        top_k=3,
    )

    if not state.policy_context:
        state.fail("No compensation policy was retrieved")
        return state

    state.mark_completed("retrieve_compensation_policy")
    return state


def request_hitl_approval(state: CompensationState) -> CompensationState:
    state.current_node = "request_hitl_approval"

    if state.status == "failed":
        return state

    if state.compensation_amount <= HITL_THRESHOLD:
        state.mark_completed("request_hitl_approval")
        return state

    state.pause_for_hitl()
    state.mark_completed("request_hitl_approval")
    return state


def apply_decision(state: CompensationState) -> CompensationState:
    state.current_node = "apply_decision"

    if state.status == "failed":
        return state

    if state.requires_hitl and state.hitl_decision is None:
        state.pause_for_hitl()
        return state

    if state.hitl_decision == "rejected":
        state.reject()
        state.mark_completed("apply_decision")
        return state

    state.approve()
    state.mark_completed("apply_decision")
    return state
