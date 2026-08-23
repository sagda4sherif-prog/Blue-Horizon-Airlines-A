from langgraph.graph import END, START, StateGraph

from .nodes import (
    analyze_disruption,
    apply_admin_decision,
    execute_recovery,
    initialize_recovery,
    request_admin_approval,
)
from .state import FlightRecoveryState


def route_after_evaluation(
    state: FlightRecoveryState,
) -> str:
    if state.get("hitl_required"):
        return "request_admin_approval"

    return "execute_recovery"


def route_after_approval(
    state: FlightRecoveryState,
) -> str:
    if state.get("hitl_decision") is None:
        return END

    return "apply_admin_decision"


def route_after_decision(
    state: FlightRecoveryState,
) -> str:
    if state.get("status") == "rejected":
        return END

    return "execute_recovery"


def build_flight_recovery_graph():
    graph = StateGraph(FlightRecoveryState)

    graph.add_node(
        "initialize_recovery",
        initialize_recovery,
    )

    graph.add_node(
        "analyze_disruption",
        analyze_disruption,
    )

    graph.add_node(
        "evaluate_recovery",
        evaluate_recovery,
    )

    graph.add_node(
        "request_admin_approval",
        request_admin_approval,
    )

    graph.add_node(
        "apply_admin_decision",
        apply_admin_decision,
    )

    graph.add_node(
        "execute_recovery",
        execute_recovery,
    )

    graph.add_edge(
        START,
        "initialize_recovery",
    )

    graph.add_edge(
        "initialize_recovery",
        "analyze_disruption",
    )

    graph.add_edge(
        "analyze_disruption",
        "evaluate_recovery",
    )

    graph.add_conditional_edges(
        "evaluate_recovery",
        route_after_evaluation,
        {
            "request_admin_approval": "request_admin_approval",
            "execute_recovery": "execute_recovery",
        },
    )

    graph.add_conditional_edges(
        "request_admin_approval",
        route_after_approval,
        {
            "apply_admin_decision": "apply_admin_decision",
            END: END,
        },
    )

    graph.add_conditional_edges(
        "apply_admin_decision",
        route_after_decision,
        {
            "execute_recovery": "execute_recovery",
            END: END,
        },
    )

    graph.add_edge(
        "execute_recovery",
        END,
    )

    return graph.compile()
