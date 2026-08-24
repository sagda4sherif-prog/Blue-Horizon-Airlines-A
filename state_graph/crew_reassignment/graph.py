from langgraph.graph import END, StateGraph

from .nodes import (
    analyze_crew_duty,
    apply_admin_decision,
    evaluate_reassignment,
    execute_reassignment,
    initialize_reassignment,
    request_admin_approval,
)
from .state import CrewReassignmentState


def build_crew_reassignment_graph():
    graph = StateGraph(CrewReassignmentState)

    graph.add_node("initialize_reassignment", initialize_reassignment)
    graph.add_node("analyze_crew_duty", analyze_crew_duty)
    graph.add_node("evaluate_reassignment", evaluate_reassignment)
    graph.add_node("request_admin_approval", request_admin_approval)
    graph.add_node("apply_admin_decision", apply_admin_decision)
    graph.add_node("execute_reassignment", execute_reassignment)

    graph.set_entry_point("initialize_reassignment")

    graph.add_conditional_edges(
        "initialize_reassignment",
        lambda state: END if state.get("status") == "failed" else "analyze_crew_duty",
    )

    graph.add_conditional_edges(
        "analyze_crew_duty",
        lambda state: (
            END if state.get("status") == "failed" else "evaluate_reassignment"
        ),
    )

    graph.add_conditional_edges(
        "evaluate_reassignment",
        lambda state: (
            "request_admin_approval"
            if state.get("hitl_required")
            else "execute_reassignment"
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
        lambda state: (
            "execute_reassignment" if state.get("status") == "approved" else END
        ),
    )

    graph.add_edge("execute_reassignment", END)

    return graph.compile()
