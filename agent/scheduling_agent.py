# agent/scheduling_agent.py
import sys
import os
import sqlite3

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from planning.decomposition import TaskDecompositionGraph
from planning.dynamic_decomposition import DynamicTaskDecompositionGraph

class DatabaseManager:
    """Manages connection with db/blue_horizon.db for operation decisions logging"""
    def __init__(self, db_path="db/blue_horizon.db"):
        self.db_path = db_path

    def log_decision(self, flight_id: int, employee_id: int, decision: str, reason: str, risk_assessment: str):
        if not os.path.exists(self.db_path):
            print(f"[DB Warning] Database file '{self.db_path}' not found locally.")
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO OperationDecisions (flight_id, employee_id, decision, reason, risk_assessment)
                VALUES (?, ?, ?, ?, ?)
            """, (flight_id, employee_id, decision, reason, risk_assessment))
            conn.commit()
            print(f"[DB Success] Operation decision logged successfully to database.")
        except Exception as e:
            print(f"[DB Error] Failed to log decision: {e}")
        finally:
            conn.close()

class SchedulingAgent:
    def __init__(self, mcp_client=None):
        self.mcp_client = mcp_client
        self.db_manager = DatabaseManager()

    def run_disrupted_flight_workflow(self, flight_id_str: str, db_flight_id: int = 3, employee_id: int = 1):
        """Runs workflow demonstrating the Divergence Case between Static and Dynamic DAGs with DB integration"""
        print("=== [Member 1: Divergence Case Demonstration] ===")
        
        # 1. Static Decomposition (Blind execution path)
        print("\n--- Running Static Decomposition (Blind Execution) ---")
        static_dag = TaskDecompositionGraph()
        static_dag.add_task("s_task_1", "Fetch cancelled flight passenger list")
        static_dag.add_task("s_task_2", "Book premium seat (Static Plan)", dependencies=["s_task_1"])
        static_dag.add_task("s_task_3", "Notify passenger", dependencies=["s_task_2"])
        print(f"Static Execution Order: {static_dag.get_execution_order()}")
        print("Static Status: Continues blindly even if premium seat booking fails.")

        # 2. Dynamic Decomposition (Adaptive path with Divergence Case)
        print("\n--- Running Dynamic Decomposition (Adaptive Path) ---")
        dyn_dag = DynamicTaskDecompositionGraph()
        dyn_dag.add_task("task_1", f"Fetch passenger list for cancelled flight {flight_id_str}")
        dyn_dag.add_task("task_2", "Attempt premium seat booking via MCP tool", dependencies=["task_1"])
        
        divergence_handled = False
        
        while True:
            ready_tasks = dyn_dag.get_next_executable_tasks()
            if not ready_tasks:
                break
                
            for task_id in ready_tasks:
                print(f"Executing Member 1 Task: {task_id}")
                if task_id == "task_2":
                    print("-> Observation: Premium seat unavailable! Dynamic engine rerouting...")
                    dyn_dag.update_task_status(task_id, "failed")
                    
                    # Dynamically inject fallback branch
                    dyn_dag.add_task("task_fallback", "Automatically switch to standard seat booking branch", dependencies=["task_1"])
                    divergence_handled = True
                    
                    # Log fallback decision into the database (matching OperationDecisions schema)[cite: 1]
                    self.db_manager.log_decision(
                        flight_id=db_flight_id,
                        employee_id=employee_id,
                        decision="Assign Backup Aircraft",
                        reason="Premium seat booking failed; dynamically rerouted to standard booking branch.",
                        risk_assessment="Low operational risk after dynamic fallback task execution."
                    )
                elif task_id == "task_fallback":
                    dyn_dag.update_task_status(task_id, "completed")
                    print("-> Alternative seat booked successfully.")
                else:
                    dyn_dag.update_task_status(task_id, "completed")

        return {"status": "success", "divergence_handled": divergence_handled, "flight_id": flight_id_str}