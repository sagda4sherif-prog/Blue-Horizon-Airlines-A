from langgraph.graph import END, StateGraph

from .nodes import (
    apply_decision,
    calculate_compensation,
    initialize_claim,
    issue_payout,
    request_hitl_approval,
    retrieve_compensation_policy,
    validate_request,
)
from .state import CompensationState


def build_flight_compensation_graph():
    graph = StateGraph(CompensationState)

    graph.add_node("initialize_claim", initialize_claim)
    graph.add_node("validate_request", validate_request)
    graph.add_node("retrieve_compensation_policy", retrieve_compensation_policy)
    graph.add_node("calculate_compensation", calculate_compensation)
    graph.add_node("request_hitl_approval", request_hitl_approval)
    graph.add_node("apply_decision", apply_decision)
    graph.add_node("issue_payout", issue_payout)

    graph.set_entry_point("initialize_claim")

    graph.add_conditional_edges(
        "initialize_claim",
        lambda state: END if state.get("status") == "failed" else "validate_request",
    )
    graph.add_conditional_edges(
        "validate_request",
        lambda state: (
            END if state.get("status") == "failed" else "retrieve_compensation_policy"
        ),
    )
    graph.add_edge("retrieve_compensation_policy", "calculate_compensation")

    graph.add_conditional_edges(
        "calculate_compensation",
        lambda state: (
            "request_hitl_approval" if state.get("hitl_required") else "apply_decision"
        ),
    )

    graph.add_conditional_edges(
        "request_hitl_approval",
        lambda state: (
            "apply_decision" if state.get("hitl_request_id") is not None else END
        ),
    )

    graph.add_conditional_edges(
        "apply_decision",
        lambda state: "issue_payout" if state.get("status") == "approved" else END,
    )

    graph.add_edge("issue_payout", END)

    return graph.compile()
