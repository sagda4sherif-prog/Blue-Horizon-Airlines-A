from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CompensationState:
    flight_id: Optional[int] = None
    passenger_id: Optional[int] = None
    cancellation_reason: str = ""
    compensation_amount: float = 0.0

    policy_context: list[str] = field(default_factory=list)
    eligibility: Optional[bool] = None

    status: str = "pending"

    requires_hitl: bool = False
    hitl_decision: Optional[str] = None

    ticket_id: Optional[str] = None
    error: Optional[str] = None

    current_node: str = "start"
    completed_nodes: list[str] = field(default_factory=list)

    def mark_completed(self, node_name: str):
        if node_name not in self.completed_nodes:
            self.completed_nodes.append(node_name)

    def fail(self, message: str):
        self.status = "failed"
        self.error = message

    def pause_for_hitl(self):
        self.status = "waiting_for_approval"
        self.requires_hitl = True

    def approve(self):
        self.hitl_decision = "approved"
        self.requires_hitl = False
        self.status = "approved"

    def reject(self):
        self.hitl_decision = "rejected"
        self.requires_hitl = False
        self.status = "rejected"
