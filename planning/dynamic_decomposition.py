# planning/dynamic_decomposition.py
import networkx as nx

class DynamicTaskDecompositionGraph:
    def __init__(self):
        self.dag = nx.DiGraph()

    def add_task(self, task_id: str, description: str, dependencies: list = None):
        dependencies = dependencies or []
        
        # 1. Add the node first to the graph if it doesn't exist
        if not self.dag.has_node(task_id):
            self.dag.add_node(task_id, description=description, status='pending')
            
        # 2. Add dependencies (edges)
        for dep in dependencies:
            self.dag.add_edge(dep, task_id)
        
        # 3. Verify acyclicity
        if not nx.is_directed_acyclic_graph(self.dag):
            for dep in dependencies:
                self.dag.remove_edge(dep, task_id)
            if task_id in self.dag and not list(self.dag.predecessors(task_id)) and not list(self.dag.successors(task_id)):
                self.dag.remove_node(task_id)
            raise ValueError(f"Cycle detected when adding task {task_id}")
        
        # 4. Safely update description and status
        self.dag.nodes[task_id]['description'] = description
        self.dag.nodes[task_id]['status'] = 'pending'

    def get_next_executable_tasks(self):
        """Determine next tasks dynamically based on current node statuses"""
        ready = []
        for node in self.dag.nodes():
            if self.dag.nodes[node].get('status', 'pending') == 'pending':
                preds = list(self.dag.predecessors(node))
                if all(self.dag.nodes[p].get('status') == 'completed' for p in preds):
                    ready.append(node)
        return ready

    def update_task_status(self, task_id: str, status: str):
        if task_id in self.dag:
            self.dag.nodes[task_id]['status'] = status