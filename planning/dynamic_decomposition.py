# planning/dynamic_decomposition.py
import networkx as nx

class DynamicTaskDecompositionGraph:
    def __init__(self):
        self.dag = nx.DiGraph()

    def add_task(self, task_id: str, description: str, dependencies: list = None):
        """Add a dynamic task ensuring acyclicity and status tracking"""
        dependencies = dependencies or []
        
        if not self.dag.has_node(task_id):
            self.dag.add_node(task_id, description=description, status="pending")
            
        for dep in dependencies:
            self.dag.add_edge(dep, task_id)
        
        if not nx.is_directed_acyclic_graph(self.dag):
            for dep in dependencies:
                self.dag.remove_edge(dep, task_id)
            if task_id in self.dag and not list(self.dag.predecessors(task_id)) and not list(self.dag.successors(task_id)):
                self.dag.remove_node(task_id)
            raise ValueError(f"Error: Adding task '{task_id}' creates a cycle in the dynamic DAG!")
        
        self.dag.nodes[task_id]['description'] = description

    def update_task_status(self, task_id: str, status: str):
        """Update task status ('pending', 'completed', 'failed')"""
        if self.dag.has_node(task_id):
            self.dag.nodes[task_id]['status'] = status

    def get_next_executable_tasks(self):
        """Return list of pending tasks whose dependencies are completed"""
        executable = []
        for node in self.dag.nodes:
            if self.dag.nodes[node]['status'] == "pending":
                predecessors = list(self.dag.predecessors(node))
                if all(self.dag.nodes[p]['status'] == "completed" for p in predecessors):
                    executable.append(node)
        return executable