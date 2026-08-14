import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.insert(0, project_root)

from agent.scheduling_agent import SchedulingAgent

def test_agent_workflow():
    print("Initializing Scheduling Agent...")
    agent = SchedulingAgent(mcp_client=None)
    
    print("\n--- Testing Static Decomposition ---")
    static_res = agent.run_disrupted_flight_workflow("FL-100")
    print(f"Static Result: {static_res}")

if __name__ == "__main__":
    test_agent_workflow()
    print("Agent test completed successfully!")