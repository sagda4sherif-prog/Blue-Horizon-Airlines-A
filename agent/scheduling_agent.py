import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from planning.decomposition import TaskDecompositionGraph
from planning.dynamic_decomposition import DynamicTaskDecompositionGraph

class SchedulingAgent:
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client

    def run_disrupted_flight_workflow(self, flight_id: str):
        """Runs dynamic workflow for disrupted flight rescheduling via MCP tools"""
        dyn_dag = DynamicTaskDecompositionGraph()
        
        dyn_dag.add_task("task_1", f"Fetch passenger list for cancelled flight {flight_id}")
        dyn_dag.add_task("task_2", "Check seat availability on alternative flight via MCP", dependencies=["task_1"])
        dyn_dag.add_task("task_3", "Book alternative seat or trigger fallback", dependencies=["task_2"])

        while True:
            ready_tasks = dyn_dag.get_next_executable_tasks()
            if not ready_tasks:
                break
                
            for task_id in ready_tasks:
                print(f"Executing Member 1 Task: {task_id}")
                # محاكاة الاتصال بأدوات الـ MCP الفعلية
                if task_id == "task_2":
                    # سيتم استبدالها لاحقاً بالاتصال الفعلي بأدوات الـ MCP
                    dyn_dag.update_task_status(task_id, "completed")
                else:
                    dyn_dag.update_task_status(task_id, "completed")
        return {"status": "success", "flight_id": flight_id}