# agent/scheduling_agent.py
import logging
import os
import sqlite3

from planning.models import Plan, Task

logger = logging.getLogger("SchedulingAgent")


class DatabaseManager:
    """Manages operation-decision logging in the Blue Horizon database."""

    def __init__(self, db_path="db/blue_horizon.db"):
        self.db_path = db_path

    def log_decision(
        self,
        flight_id: int,
        employee_id: int,
        decision: str,
        reason: str,
        risk_assessment: str,
    ):
        if not os.path.exists(self.db_path):
            logger.warning(
                "Database file '%s' not found locally.",
                self.db_path,
            )
            return

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO OperationDecisions
                (flight_id, employee_id, decision, reason, risk_assessment)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    flight_id,
                    employee_id,
                    decision,
                    reason,
                    risk_assessment,
                ),
            )
            conn.commit()
            logger.info("Operation decision logged successfully.")
        except Exception as exc:
            logger.error("Failed to log decision: %s", exc)
        finally:
            conn.close()


class SchedulingAgent:
    """
    Scheduling agent integrating the Planning Toolkit with MCP tools.

    The workflow uses the new Plan/Task DAG model and dynamically
    creates a fallback plan when an operational action fails.
    """

    def __init__(self, mcp_client=None):
        self.mcp_client = mcp_client
        self.db_manager = DatabaseManager()

    def execute_tool(self, tool_name: str, arguments: dict) -> dict:
        """
        Execute an MCP tool when a client is available.

        For local divergence-case tests, a deterministic mock fallback
        is used when no MCP client is supplied.
        """
        logger.info(
            "Executing tool '%s' with args: %s",
            tool_name,
            arguments,
        )

        if self.mcp_client is not None:
            try:
                response = self.mcp_client.call_tool(
                    tool_name,
                    arguments,
                )

                if isinstance(response, dict):
                    return response

                return {
                    "status": "success",
                    "data": response,
                }

            except Exception as exc:
                logger.error(
                    "MCP tool execution failed: %s",
                    exc,
                )
                return {
                    "status": "failed",
                    "reason": str(exc),
                }

        # Deterministic mock behavior for the divergence case.
        if "premium" in tool_name.lower():
            return {
                "status": "failed",
                "reason": "Seat unavailable: Premium cabin capacity full",
            }

        return {
            "status": "success",
            "data": "Executed successfully",
        }

    def _build_static_plan(self, flight_id_str: str) -> Plan:
        return Plan(
            goal=f"Resolve disrupted flight {flight_id_str}",
            tasks=[
                Task(
                    id="fetch_passengers",
                    instruction="Fetch the cancelled flight passenger list",
                    depends_on=[],
                ),
                Task(
                    id="premium_booking",
                    instruction="Book a premium seat for the affected passenger",
                    depends_on=["fetch_passengers"],
                ),
                Task(
                    id="notify_passenger",
                    instruction="Notify the passenger after the booking decision",
                    depends_on=["premium_booking"],
                ),
            ],
        )

    def _build_fallback_plan(self, flight_id_str: str) -> Plan:
        return Plan(
            goal=f"Resolve disrupted flight {flight_id_str} using fallback routing",
            tasks=[
                Task(
                    id="fetch_passengers",
                    instruction="Fetch the cancelled flight passenger list",
                    depends_on=[],
                ),
                Task(
                    id="standard_booking",
                    instruction="Book a standard seat as the operational fallback",
                    depends_on=["fetch_passengers"],
                ),
                Task(
                    id="notify_passenger",
                    instruction="Notify the passenger after the fallback booking",
                    depends_on=["standard_booking"],
                ),
            ],
        )

    def _log_fallback_decision(
        self,
        db_flight_id: int,
        employee_id: int,
        reason_msg: str,
    ):
        self.db_manager.log_decision(
            flight_id=db_flight_id,
            employee_id=employee_id,
            decision="Assign Standard Seat Fallback",
            reason=(
                "Premium seat booking failed "
                f"({reason_msg}); dynamically rerouted to standard booking branch."
            ),
            risk_assessment=(
                "Low operational risk after dynamic fallback task execution."
            ),
        )

    def run_disrupted_flight_workflow(
        self,
        flight_id_str: str,
        db_flight_id: int = 3,
        employee_id: int = 1,
    ):
        """
        Demonstrate the divergence case using the new Planning Toolkit.

        A static plan initially chooses premium booking. If the operational
        tool fails, a new fallback DAG is constructed and executed.
        """
        logger.info(
            "=== Divergence Case Demonstration with Planning + MCP ==="
        )

        # ---------------------------------------------------------
        # 1. Static planning
        # ---------------------------------------------------------
        static_plan = self._build_static_plan(flight_id_str)

        logger.info(
            "Static execution order: %s",
            static_plan.topological_order(),
        )
        logger.info(
            "Static execution batches: %s",
            static_plan.execution_batches(),
        )

        # ---------------------------------------------------------
        # 2. Execute the premium-booking branch
        # ---------------------------------------------------------
        premium_response = self.execute_tool(
            "book_premium_seat",
            {"flight_id": flight_id_str},
        )

        if premium_response.get("status") != "failed":
            return {
                "status": "success",
                "divergence_handled": False,
                "flight_id": flight_id_str,
                "plan": static_plan.model_dump(),
            }

        reason_msg = premium_response.get(
            "reason",
            "Unknown failure",
        )

        logger.warning(
            "Premium booking failed: %s. Injecting fallback plan.",
            reason_msg,
        )

        # ---------------------------------------------------------
        # 3. Dynamic fallback planning
        # ---------------------------------------------------------
        fallback_plan = self._build_fallback_plan(flight_id_str)

        self._log_fallback_decision(
            db_flight_id=db_flight_id,
            employee_id=employee_id,
            reason_msg=reason_msg,
        )

        fallback_response = self.execute_tool(
            "book_standard_seat",
            {"flight_id": flight_id_str},
        )

        if fallback_response.get("status") != "success":
            return {
                "status": "failed",
                "divergence_handled": True,
                "flight_id": flight_id_str,
                "fallback_response": fallback_response,
                "plan": fallback_plan.model_dump(),
            }

        logger.info(
            "Fallback standard seat booked successfully."
        )

        return {
            "status": "success",
            "divergence_handled": True,
            "flight_id": flight_id_str,
            "plan": fallback_plan.model_dump(),
        }