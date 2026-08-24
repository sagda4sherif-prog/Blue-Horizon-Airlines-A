from dataclasses import dataclass
from typing import Any


@dataclass
class CompensationState:
    flight_id: int
    passenger_id: int
    cancellation_reason: str

    compensation_amount: float = 0.0
    policy_context: str = ""

    status: str = "pending"
    approved: bool = False

    error: str | None = None
    ticket_id: str | None = None

    current_node: str = "start"

    metadata: dict[str, Any] | None = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def fail(self, error: str):
        self.error = error
        self.status = "failed"
        self.current_node = "error"

    def wait_for_approval(self):
        self.status = "waiting_for_approval"
        self.current_node = "hitl"

    def approve(self):
        self.approved = True
        self.status = "approved"
        self.current_node = "approval"

    def reject(self):
        self.approved = False
        self.status = "rejected"
        self.current_node = "approval"

    def complete(self):
        self.status = "completed"
        self.current_node = "completed"

    def to_dict(self):
        return {
            "flight_id": self.flight_id,
            "passenger_id": self.passenger_id,
            "cancellation_reason": self.cancellation_reason,
            "compensation_amount": self.compensation_amount,
            "policy_context": self.policy_context,
            "status": self.status,
            "approved": self.approved,
            "error": self.error,
            "ticket_id": self.ticket_id,
            "current_node": self.current_node,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            flight_id=data["flight_id"],
            passenger_id=data["passenger_id"],
            cancellation_reason=data["cancellation_reason"],
            compensation_amount=data.get(
                "compensation_amount",
                0.0,
            ),
            policy_context=data.get(
                "policy_context",
                "",
            ),
            status=data.get(
                "status",
                "pending",
            ),
            approved=data.get(
                "approved",
                False,
            ),
            error=data.get("error"),
            ticket_id=data.get("ticket_id"),
            current_node=data.get(
                "current_node",
                "start",
            ),
            metadata=data.get(
                "metadata",
                {},
            ),
        )
