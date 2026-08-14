# planning/decomposition.py
import networkx as nx

class TaskDecompositionGraph:
    def __init__(self):
        self.dag = nx.DiGraph()

    def add_task(self, task_id: str, description: str, dependencies: list = None):
        """Add a task ensuring no cycles are created (Acyclicity Enforcement)"""
        dependencies = dependencies or []
        for dep in dependencies:
            self.dag.add_edge(dep, task_id)
        
        # Verify acyclicity
        if not nx.is_directed_acyclic_graph(self.dag):
            for dep in dependencies:
                self.dag.remove_edge(dep, task_id)
            raise ValueError(f"Error: Adding task '{task_id}' creates a cycle in the DAG!")
        
        self.dag.nodes[task_id]['description'] = description

    def get_execution_order(self):
        """Return topological sort order for static execution"""
        return list(nx.topological_sort(self.dag))