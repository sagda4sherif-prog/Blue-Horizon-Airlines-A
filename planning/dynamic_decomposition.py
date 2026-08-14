# planning/dynamic_dynamic_decomposition.py or dynamic_decomposition.py
import networkx as nx

class DynamicTaskDecompositionGraph:
    def __init__(self):
        self.dag = nx.DiGraph()

    def add_task(self, task_id: str, description: str, dependencies: list = None):
        dependencies = dependencies or []
        for dep in dependencies:
            self.dag.add_edge(dep, task_id)
        
        if not nx.is_directed_acyclic_graph(self.dag):
            for dep in dependencies:
                self.dag.remove_edge(dep, task_id)
            raise ValueError(f"Cycle detected when adding task {task_id}")
        
        self.dag.nodes[task_id]['description'] = description
        self.dag.nodes[task_id]['status'] = 'pending'  # pending, completed, failed

    def get_next_executable_tasks(self):
        """Determine next tasks dynamically based on current node statuses"""
        ready = []
        for node in self.dag.nodes():
            if self.dag.nodes[node]['status'] == 'pending':
                preds = list(self.dag.predecessors(node))
                if all(self.dag.nodes[p]['status'] == 'completed' for p in preds):
                    ready.append(node)
        return ready

    def update_task_status(self, task_id: str, status: str):
        if task_id in self.dag:
            self.dag.nodes[task_id]['status'] = status