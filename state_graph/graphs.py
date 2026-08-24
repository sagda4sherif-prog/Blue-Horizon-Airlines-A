from langgraph.graph import END, StateGraph

from .compensation_nodes import (
    validate_request,
    calculate_compensation,
    retrieve_compensation_policy,
    request_hitl_approval,
    apply_decision,
)
from .compensation_state import CompensationState
from .checkpoint import CompensationCheckpoint
from .tickets import TicketManager
from .nodes import (
    initialize_recovery,
    analyze_disruption,
    evaluate_recovery,
    request_admin_approval,
    apply_admin_decision,
    execute_recovery,
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
            "request_admin_approval"
            if state.get("hitl_required")
            else "execute_recovery"
        ),
    )

    graph.add_conditional_edges(
        "request_admin_approval",
        lambda state: (
            "apply_admin_decision"
            if state.get("hitl_decision") is not None
            else END
        ),
    )

    graph.add_conditional_edges(
        "apply_admin_decision",
        lambda state: (
            "execute_recovery"
            if state.get("status") == "approved"
            else END
        ),
    )

    graph.add_edge("execute_recovery", END)

    return graph.compile()


class CompensationGraph:
    def __init__(self, rag_pipeline=None):
        self.rag_pipeline = rag_pipeline
        self.checkpoint = CompensationCheckpoint()
        self.tickets = TicketManager()

    def run(self, state: CompensationState) -> CompensationState:
        try:
            state = validate_request(state)
            self.checkpoint.save(state)

            if state.status == "failed":
                return self._create_failure_ticket(state)

            state = calculate_compensation(state)
            self.checkpoint.save(state)

            if state.status == "failed":
                return self._create_failure_ticket(state)

            state = retrieve_compensation_policy(
                state,
                self.rag_pipeline,
            )
            self.checkpoint.save(state)

            if state.status == "failed":
                return self._create_failure_ticket(state)

            state = request_hitl_approval(state)
            self.checkpoint.save(state)

            if state.status == "waiting_for_approval":
                return state

            state = apply_decision(state)
            self.checkpoint.save(state)

            if state.status == "failed":
                return self._create_failure_ticket(state)

            return state

        except Exception as exc:
            state.fail(str(exc))
            return self._create_failure_ticket(state)

    def resume(self, flight_id: int):
        state = self.checkpoint.load_latest(flight_id)

        if state is None:
            return None

        if state.status == "waiting_for_approval":
            return state

        return self.run(state)

    def approve(self, flight_id: int):
        state = self.checkpoint.load_latest(flight_id)

        if state is None:
            return None

        state.approve()
        self.checkpoint.save(state)

        return self.run(state)

    def reject(self, flight_id: int):
        state = self.checkpoint.load_latest(flight_id)

        if state is None:
            return None

        state.reject()
        self.checkpoint.save(state)

        return state

    def _create_failure_ticket(self, state):
        if state.ticket_id is None:
            state.ticket_id = self.tickets.create_ticket(
                flight_id=state.flight_id,
                error_type="GRAPH_EXECUTION_ERROR",
                error_message=state.error or "Unknown graph error",
            )

        state.status = "failed"
        self.checkpoint.save(state)

        return state
