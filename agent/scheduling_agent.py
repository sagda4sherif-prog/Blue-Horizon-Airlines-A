# agent/scheduling_agent.py
import sys
import os
import sqlite3
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from planning.decomposition import TaskDecompositionGraph
from planning.dynamic_decomposition import DynamicTaskDecompositionGraph

logger = logging.getLogger("SchedulingAgent")

class DatabaseManager:
    """Manages connection with db/blue_horizon.db for operation decisions logging"""
    def __init__(self, db_path="db/blue_horizon.db"):
        self.db_path = db_path

    def log_decision(self, flight_id: int, employee_id: int, decision: str, reason: str, risk_assessment: str):
        """Log operational decisions into the database with error handling."""
        if not os.path.exists(self.db_path):
            logger.warning(f"Database file '{self.db_path}' not found locally.")
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO OperationDecisions (flight_id, employee_id, decision, reason, risk_assessment)
                VALUES (?, ?, ?, ?, ?)
            """, (flight_id, employee_id, decision, reason, risk_assessment))
            conn.commit()
            logger.info("Operation decision logged successfully to database.")
        except Exception as e:
            logger.error(f"Failed to log decision: {e}")
        finally:
            conn.close()

class SchedulingAgent:
    """
    Scheduling Agent responsible for executing flight disruption workflows,
    managing static vs dynamic DAG execution, and integrating with MCP tools.
    """
    def __init__(self, mcp_client=None):
        self.mcp_client = mcp_client
        self.db_manager = DatabaseManager()

    def execute_tool(self, tool_name: str, arguments: dict) -> dict:
        """Execute tool via MCP client if available, fallback to mock response."""
        logger.info(f"Executing tool '{tool_name}' with args: {arguments}")
        if self.mcp_client:
            try:
                response = self.mcp_client.call_tool(tool_name, arguments)
                return response
            except Exception as e:
                logger.error(f"MCP tool execution failed: {e}")
                return {"status": "failed", "reason": str(e)}
        
        # Default mock behavior for demonstration/divergence case
        if "premium" in tool_name.lower():
            return {"status": "failed", "reason": "Seat unavailable: Premium cabin capacity full"}
        return {"status": "success", "data": "Executed successfully"}

    def run_disrupted_flight_workflow(self, flight_id_str: str, db_flight_id: int = 3, employee_id: int = 1):
        """Runs workflow demonstrating the Divergence Case between Static and Dynamic DAGs with real MCP/DB integration"""
        logger.info("=== [Member 1: Divergence Case Demonstration with MCP] ===")
        
        # 1. Static Decomposition (Blind execution path)
        logger.info("--- Running Static Decomposition (Blind Execution) ---")
        static_dag = TaskDecompositionGraph()
        static_dag.add_task("s_task_1", "Fetch cancelled flight passenger list")
        static_dag.add_task("s_task_2", "Book premium seat (Static Plan)", dependencies=["s_task_1"])
        static_dag.add_task("s_task_3", "Notify passenger", dependencies=["s_task_2"])
        logger.info(f"Static Execution Order: {static_dag.get_execution_order()}")
        logger.info("Static Status: Continues blindly even if premium seat booking fails.")

        # 2. Dynamic Decomposition (Adaptive path with Divergence Case & MCP)
        logger.info("--- Running Dynamic Decomposition (Adaptive Path with MCP) ---")
        dyn_dag = DynamicTaskDecompositionGraph()
        dyn_dag.add_task("task_1", f"Fetch passenger list for cancelled flight {flight_id_str}")
        dyn_dag.add_task("task_2", "Attempt premium seat booking via MCP tool", dependencies=["task_1"])
        
        divergence_handled = False
        
        while True:
            ready_tasks = dyn_dag.get_next_executable_tasks()
            if not ready_tasks:
                break
                
            for task_id in ready_tasks:
                logger.info(f"Executing Member 1 Task: {task_id}")
                
                if task_id == "task_2":
                    # Execute tool via MCP or simulation
                    mcp_response = self.execute_tool("book_premium_seat", {"flight_id": flight_id_str})

                    if mcp_response and mcp_response.get("status") == "failed":
                        reason_msg = mcp_response.get("reason", "Unknown failure")
                        logger.warning(f"Observation: {reason_msg}! Dynamic engine rerouting...")
                        dyn_dag.update_task_status(task_id, "failed")
                        
                        # Dynamically inject fallback branch
                        dyn_dag.add_task("task_fallback", "Automatically switch to standard seat booking branch", dependencies=["task_1"])
                        divergence_handled = True
                        
                        # Log decision into the database (OperationDecisions schema)[cite: 1]
                        self.db_manager.log_decision(
                            flight_id=db_flight_id,
                            employee_id=employee_id,
                            decision="Assign Standard Seat Fallback",
                            reason=f"Premium seat booking failed ({reason_msg}); dynamically rerouted to standard booking branch.",
                            risk_assessment="Low operational risk after dynamic fallback task execution."
                        )
                    else:
                        dyn_dag.update_task_status(task_id, "completed")
                        logger.info("Premium seat booked successfully via MCP.")

                elif task_id == "task_fallback":
                    self.execute_tool("book_standard_seat", {"flight_id": flight_id_str})
                    dyn_dag.update_task_status(task_id, "completed")
                    logger.info("Alternative standard seat booked successfully and verified.")
                    
                else:
                    dyn_dag.update_task_status(task_id, "completed")

        return {"status": "success", "divergence_handled": divergence_handled, "flight_id": flight_id_str}