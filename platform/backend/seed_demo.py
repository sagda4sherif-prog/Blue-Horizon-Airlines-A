"""
Run after run_platform_backend.py has created the tables at least once
(or just run ensure_platform_schema() here too — it's idempotent):

    python -c "from run_platform_backend import *; import backend.seed_demo"

or simpler, from the project root with sys.path already fixed up:

    python run_platform_backend.py   # start it once so tables exist, then Ctrl+C
    PYTHONPATH=platform python platform/backend/seed_demo.py

This inserts ONE fake ticket and ONE fake HITL request through the
exact same graph_bridge functions state_graph/ will call for real, so
the admin tickets/HITL screens have something to show before Persons
1/2/3's graphs exist. Safe to run multiple times — it's demo data, not
part of the schema.
"""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "platform"))

from backend.db import ensure_platform_schema
from backend.graph_bridge import create_ticket, create_hitl_request


def main():
    ensure_platform_schema()

    ticket_id = create_ticket(
        graph_name="flight_compensation",
        run_id="demo-run-001",
        node_name="submit_claim",
        failure_type="tool_error",
        description=(
            "Insurer claims endpoint returned a malformed response "
            "while submitting the compensation claim for flight BH204."
        ),
        checkpoint_state={
            "flight_id": 204,
            "passenger_count": 3,
            "claim_amount": 620,
            "step": "submit_claim",
        },
    )

    hitl_id = create_hitl_request(
        graph_name="flight_compensation",
        run_id="demo-run-002",
        node_name="approve_payout",
        reason="compensation_amount_exceeds_threshold",
        summary="Approve $850 payout for flight BH117 (above the $500 auto-approval limit)?",
        checkpoint_state={
            "flight_id": 117,
            "proposed_amount": 850,
            "threshold": 500,
        },
    )

    print(f"Seeded demo ticket #{ticket_id} and HITL request #{hitl_id}")


if __name__ == "__main__":
    main()
