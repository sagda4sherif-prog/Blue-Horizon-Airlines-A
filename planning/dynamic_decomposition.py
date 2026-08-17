# planning/dynamic_decomposition.py
import networkx as nx
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("DynamicDAGManager")

class DynamicTaskDecompositionGraph:
    """
    Dynamic DAG manager that handles task decomposition, 
    failure handling, and rerouting while enforcing acyclicity.
    """
    def __init__(self):
        self.dag = nx.DiGraph()

    def add_task(self, task_id: str, description: str, dependencies: List[str] = None):
        """Add a dynamic task ensuring acyclicity and status tracking"""
        dependencies = dependencies or []
        
        test_graph = self.dag.copy()
        if not test_graph.has_node(task_id):
            test_graph.add_node(task_id, description=description, status="pending")
            
        for dep in dependencies:
            test_graph.add_edge(dep, task_id)
        
        if not nx.is_directed_acyclic_graph(test_graph):
            raise ValueError(f"Error: Adding task '{task_id}' creates a cycle in the dynamic DAG!")
        
        self.dag = test_graph
        logger.info(f"Task '{task_id}' added successfully. Acyclicity verified.")

    def update_task_status(self, task_id: str, status: str):
        """Update task status ('pending', 'completed', 'failed')"""
        if self.dag.has_node(task_id):
            self.dag.nodes[task_id]['status'] = status

    def get_next_executable_tasks(self) -> List[str]:
        """Return list of pending tasks whose dependencies are completed"""
        executable = []
        for node in self.dag.nodes:
            if self.dag.nodes[node]['status'] == "pending":
                predecessors = list(self.dag.predecessors(node))
                if all(self.dag.nodes[p]['status'] == "completed" for p in predecessors):
                    executable.append(node)
        return executable

    def handle_failure(self, failed_task_id: str, reason: str) -> Optional[str]:
        """
        Handle task failure, update its status, and dynamically generate a fallback branch.
        """
        if failed_task_id not in self.dag:
            logger.error(f"Task '{failed_task_id}' not found in DAG.")
            return None

        self.update_task_status(failed_task_id, "failed")
        self.dag.nodes[failed_task_id]["error_reason"] = reason
        logger.warning(f"Task '{failed_task_id}' failed due to: {reason}. Triggering dynamic fallback...")

        fallback_task_id = f"fallback_{failed_task_id}"
        
        if "seat unavailable" in reason.lower() or "premium" in reason.lower() or "capacity" in reason.lower():
            fallback_desc = "Automatically switch to standard seat booking branch"
        else:
            fallback_desc = f"Execute alternative fallback routing for reason: {reason}"

        try:
            predecessors = list(self.dag.predecessors(failed_task_id))
            self.add_task(
                task_id=fallback_task_id,
                description=fallback_desc,
                dependencies=predecessors if predecessors else []
            )
            logger.info(f"Fallback task '{fallback_task_id}' successfully created and injected into DAG.")
            return fallback_task_id
        except Exception as e:
            logger.critical(f"Failed to generate dynamic fallback: {str(e)}")
            return None