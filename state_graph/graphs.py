from state_graph.compensation_nodes import (
    validate_request,
    calculate_compensation,
    retrieve_compensation_policy,
    request_hitl_approval,
    apply_decision,
)
from state_graph.compensation_state import CompensationState
from state_graph.checkpoint import CompensationCheckpoint
from state_graph.tickets import TicketManager


class CompensationGraph:
    def __init__(self, rag_pipeline=None):
        self.rag_pipeline = rag_pipeline
        self.checkpoint = CompensationCheckpoint()
        self.tickets = TicketManager()

    def run(
        self,
        state: CompensationState,
    ) -> CompensationState:

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

    def resume(
        self,
        flight_id: int,
    ) -> CompensationState | None:

        state = self.checkpoint.load_latest(flight_id)

        if state is None:
            return None

        if state.status == "waiting_for_approval":
            return state

        return self.run(state)

    def approve(
        self,
        flight_id: int,
    ) -> CompensationState | None:

        state = self.checkpoint.load_latest(flight_id)

        if state is None:
            return None

        state.approve()
        self.checkpoint.save(state)

        return self.run(state)

    def reject(
        self,
        flight_id: int,
    ) -> CompensationState | None:

        state = self.checkpoint.load_latest(flight_id)

        if state is None:
            return None

        state.reject()
        self.checkpoint.save(state)

        return state

    def _create_failure_ticket(
        self,
        state: CompensationState,
    ) -> CompensationState:

        if state.ticket_id is None:
            state.ticket_id = self.tickets.create_ticket(
                flight_id=state.flight_id,
                error_type="GRAPH_EXECUTION_ERROR",
                error_message=state.error or "Unknown graph error",
            )

        state.status = "failed"
        self.checkpoint.save(state)

        return state
