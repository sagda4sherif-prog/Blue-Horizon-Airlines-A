from langgraph.graph import END, StateGraph

from .nodes import (
    analyze_disruption,
    apply_admin_decision,
    evaluate_recovery,
    execute_recovery,
    initialize_recovery,
    request_admin_approval,
)
from .state import FlightRecoveryState


def build_flight_recovery_graph():
    graph = StateGraph(FlightRecoveryState)

    graph.add_node("initialize_recovery", initialize_recovery)
    graph.add_node("analyze_disruption", analyze_disruption)
    graph.add_node("evaluate_recovery", evaluate_recovery)
    graph.add_node("request_admin_approval", request_admin_approval)
    graph.add_node("apply_admin_decision", apply_admin_decision)
    graph.add_node("execute_recovery", execute_recovery)

    graph.set_entry_point("initialize_recovery")

    graph.add_edge("initialize_recovery", "analyze_disruption")
    graph.add_edge("analyze_disruption", "evaluate_recovery")

    graph.add_conditional_edges(
        "evaluate_recovery",
        lambda state: (
            "request_admin_approval" if state.get("hitl_required") else "execute_recovery"
        ),
    )

    graph.add_conditional_edges(
        "request_admin_approval",
        lambda state: (
            "apply_admin_decision" if state.get("hitl_request_id") is not None else END
        ),
    )

    graph.add_conditional_edges(
        "apply_admin_decision",
        lambda state: "execute_recovery" if state.get("status") == "approved" else END,
    )

    graph.add_edge("execute_recovery", END)

    return graph.compile()
