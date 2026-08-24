from typing import Any, TypedDict

GRAPH_NAME = "flight_compensation"

# Payouts at or below this line are approved automatically; above it a
# node must pause for admin sign-off (README's "no consistent record of
# who approved what, or why" problem, applied to money specifically).
HITL_THRESHOLD = 500.0


class CompensationState(TypedDict, total=False):
    run_id: str
    flight_id: int
    passenger_id: int
    cancellation_reason: str

    compensation_amount: float
    policy_context: str

    status: str
    current_node: str

    hitl_required: bool
    hitl_request_id: int | None
    hitl_decision: str | None

    ticket_id: int | None
    error: str | None

    checkpoint_ref: str | None
    metadata: dict[str, Any]
