import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

SERVER_SCRIPT_PATH = os.path.join(
    PROJECT_ROOT,
    "mcp_server",
    "server.py",
)


class MCPToolClient:
    """
    Small synchronous facade over the async MCP ClientSession.

    Each call starts a stdio MCP server session, invokes one tool,
    normalizes the result, and closes the session.
    """

    def __init__(self, server_script_path: str = SERVER_SCRIPT_PATH):
        self.server_script_path = server_script_path

    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        return asyncio.run(
            self._call_tool(tool_name, arguments)
        )

    async def _call_tool(
        self,
        tool_name: str,
        arguments: dict,
    ) -> dict:
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[self.server_script_path],
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.call_tool(
                    tool_name,
                    arguments=arguments,
                )

                return self._normalize_result(result)

    @staticmethod
    def _normalize_result(result) -> dict:
        structured = getattr(result, "structuredContent", None)

        if isinstance(structured, dict) and structured:
            return structured

        content = getattr(result, "content", None)

        if not content:
            return {
                "status": "success",
            }

        texts = []

        for item in content:
            text = getattr(item, "text", None)

            if isinstance(text, str):
                texts.append(text)

        if not texts:
            return {
                "status": "success",
            }

        text = "\n".join(texts).strip()

        try:
            parsed = json.loads(text)

            if isinstance(parsed, dict):
                return parsed

        except json.JSONDecodeError:
            pass

        return {
            "status": "success",
            "data": text,
        }