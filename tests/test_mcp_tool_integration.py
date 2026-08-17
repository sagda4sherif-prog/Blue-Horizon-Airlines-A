from agent.mcp_tool_client import MCPToolClient
from agent.scheduling_agent import SchedulingAgent


def test_mcp_send_notification():
    client = MCPToolClient()

    result = client.call_tool(
        "send_notification",
        {
            "flight_id": 3,
            "recipient": "integration-test@example.com",
            "message": "MCP integration test",
        },
    )

    assert isinstance(result, dict)
    assert result.get("success") is True


def test_scheduling_agent_uses_real_mcp_client():
    client = MCPToolClient()
    agent = SchedulingAgent(mcp_client=client)

    result = agent.execute_tool(
        "send_notification",
        {
            "flight_id": 3,
            "recipient": "scheduling-agent-test@example.com",
            "message": "SchedulingAgent MCP integration test",
        },
    )

    assert isinstance(result, dict)
    assert result.get("success") is True