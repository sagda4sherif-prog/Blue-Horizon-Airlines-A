from agent.mcp_tool_client import MCPToolClient
from agent.scheduling_agent import SchedulingAgent
from mcp_server.database import get_connection


def _cleanup_notification(recipient: str, message: str):
    conn = get_connection()

    try:
        conn.execute(
            """
            DELETE FROM Notifications
            WHERE recipient = ?
              AND message = ?
            """,
            (recipient, message),
        )
        conn.commit()
    finally:
        conn.close()


def test_mcp_send_notification():
    recipient = "integration-test@example.com"
    message = "MCP integration test"

    try:
        client = MCPToolClient()

        result = client.call_tool(
            "send_notification",
            {
                "flight_id": 3,
                "recipient": recipient,
                "message": message,
            },
        )

        assert isinstance(result, dict)
        assert result.get("success") is True

    finally:
        _cleanup_notification(recipient, message)


def test_scheduling_agent_uses_real_mcp_client():
    recipient = "scheduling-agent-test@example.com"
    message = "SchedulingAgent MCP integration test"

    try:
        client = MCPToolClient()
        agent = SchedulingAgent(mcp_client=client)

        result = agent.execute_tool(
            "send_notification",
            {
                "flight_id": 3,
                "recipient": recipient,
                "message": message,
            },
        )

        assert isinstance(result, dict)
        assert result.get("success") is True

    finally:
        _cleanup_notification(recipient, message)