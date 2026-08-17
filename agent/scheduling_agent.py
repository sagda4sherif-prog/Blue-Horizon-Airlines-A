# agent/scheduling_agent.py
import logging
import os
import sys
import sqlite3
from pathlib import Path

from planning.models import Plan, Task
from planning.environment import GroundedEnvironment
from planning.self_refine import SelfRefiner

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from reflexion import ReflexionAgent  # repo-root module; see planning/__init__.py docstring

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

    def __init__(self, mcp_client=None, environment=None):
        self.mcp_client = mcp_client
        self.db_manager = DatabaseManager()
        # Grounded EnvironmentFeedback source: real DB checks, not a model's
        # opinion of itself. Used directly (LLM-free) by
        # `run_reflexion_reassignment` below, and by `route_subtask` when a
        # real LLM is supplied for LATS.
        self.environment = environment or GroundedEnvironment()

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

    # ---------------------------------------------------------------
    # Grounded self-correction: routing, Reflexion, Self-Refine
    # ---------------------------------------------------------------

    def route_subtask(self, request: str, llm=None) -> dict:
        """Route a sub-task to Plan-and-Solve / Tree of Thoughts / grounded
        LATS via `planning.routing.PlanningRouter`.

        Imported lazily because `PlanningRouter` (and `plan_and_solve`,
        `tree_of_thoughts`, `lats`) depend on `langchain_core`, which not
        every deployment of this agent needs installed just to run the
        LLM-free grounded-Reflexion path below. Requires a real
        `BaseChatModel` — this method is for the live-agent path, not for
        tests, which exercise the grounded pieces directly instead.
        """
        if llm is None:
            raise ValueError("route_subtask requires a live chat model; see run_reflexion_reassignment for the LLM-free grounded path used in tests.")
        from planning.routing import PlanningRouter

        router = PlanningRouter(llm, environment=self.environment)
        return router.run(request)

    def evaluate_candidate(self, candidate_text: str) -> dict:
        """Grounded pass/fail on one proposed reassignment, no LLM involved.

        This is the same `GroundedEnvironment` LATS uses internally,
        exposed directly so the scheduling agent (and Reflexion, below) can
        check a candidate against the real database without paying for a
        model call.
        """
        feedback = self.environment.evaluate(candidate_text)
        return {
            "success": feedback.success,
            "score": feedback.score,
            "errors": feedback.details,
        }

    def run_reflexion_reassignment(
        self,
        flight_id_str: str,
        candidates: list[str],
        max_trials: int = 3,
    ) -> dict:
        """Reflexion over a list of candidate reassignments, grounded by the
        real database on every trial.

        Unlike `run_disrupted_flight_workflow`'s two-plan divergence demo
        (decomposition-first vs. dynamic, no retries), this is the case a
        single retry genuinely isn't enough for: several candidates in a
        row can each fail a *different* real constraint (one aircraft is
        under maintenance, the next proposed crew member is over the duty
        limit), and only carrying the accumulated episodic reflections
        forward tells the planner which candidates are already known-bad.

        The `planner` here is a deterministic stand-in for an LLM call: it
        picks the next untried candidate, skipping any name it already
        knows failed from `previous_lessons`. In the live agent this
        planner argument is replaced by a real LLM call (see
        `planning.dynamic_decomposition` for the same interleaved shape);
        the executor/grounding below is identical either way, and is what
        actually matters for the "grounded Reflexion" concern.
        """

        def planner(request, previous_lessons=None):
            tried = set()
            for lesson in previous_lessons or []:
                tried.update(lesson.get("plan", {}).get("candidate_pool_seen", []))
            remaining = [c for c in candidates if c not in tried]
            candidate = remaining[0] if remaining else candidates[-1]
            return {
                "flight_id": request["flight_id"],
                "candidate": candidate,
                "candidate_pool_seen": [c for c in candidates if c in tried] + [candidate],
            }

        def executor(plan):
            outcome = self.evaluate_candidate(plan["candidate"])
            return outcome

        agent = ReflexionAgent(planner=planner, executor=executor, max_trials=max_trials)
        result = agent.run({"flight_id": flight_id_str})
        return result

    def refine_notification(self, draft_message: str, required_facts: list[str], max_iterations: int = 3) -> dict:
        """Self-Refine loop for the cheap-to-redo sub-task: drafting the
        passenger/crew notification once a reassignment decision is made.

        Grounded, not the model grading its own prose: the validator is a
        real string-containment check against the facts the notification
        is legally/operationally required to state (new flight number,
        new departure time, the reassigned resource), not an LLM asked
        "does this notification look good?".
        """

        def validator(message: str) -> dict:
            missing = [fact for fact in required_facts if fact.lower() not in message.lower()]
            return {"valid": not missing, "errors": [f"missing required fact: {fact}" for fact in missing]}

        def reviser(message: str, errors: list[str]) -> str:
            # A real LLM call would rewrite the draft in prose; this
            # deterministic stand-in appends exactly the facts the
            # validator flagged as missing, which is enough to make the
            # revision step verifiably change the message shape being
            # tested here (see planning/self_refine.py's reviser fix).
            missing = [fact for fact in required_facts if fact.lower() not in message.lower()]
            if not missing:
                return message
            return message.rstrip() + " " + " ".join(f"[{fact}]" for fact in missing)

        refiner = SelfRefiner(validator=validator, max_iterations=max_iterations, reviser=reviser)
        return refiner.refine(draft_message)

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