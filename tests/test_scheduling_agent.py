# tests/test_scheduling_agent.py
import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from agent.scheduling_agent import SchedulingAgent

def test_divergence_case():
    print("Initializing Scheduling Agent for Divergence Case Test...")
    agent = SchedulingAgent(mcp_client=None)
    
    # Run disrupted flight workflow with database logging support[cite: 1]
    result = agent.run_disrupted_flight_workflow("FL-100", db_flight_id=3, employee_id=1)
    
    if result.get("divergence_handled") == True:
        print("\n TEST PASSED: Divergence Case (Dynamic adaptation) and DB logging successful.")
    else:
        print("\n TEST FAILED: Divergence Case not handled.")

if __name__ == "__main__":
    test_divergence_case()