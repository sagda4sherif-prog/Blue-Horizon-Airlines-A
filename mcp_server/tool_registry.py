from typing import Callable

from .mcp_app import mcp


class ToolRegistry:
    """
    Runtime registry for MCP tools.

    The functions remain available in the Python module, while
    this registry controls which tools are currently exposed
    through the MCP server.
    """

    def __init__(self):
        self._catalog: dict[str, Callable] = {}
        self._protected_tools: set[str] = {
            "authenticate_manager",
            "deauthenticate_manager",
        }

    def add_to_catalog(self, name: str, tool_fn: Callable) -> None:
        """Add a tool function to the available tool catalogue."""
        self._catalog[name] = tool_fn

    def register(self, name: str) -> None:
        """Expose a catalogued tool through the MCP server."""

        if name not in self._catalog:
            raise KeyError(f"Unknown tool: {name}")

        current_tools = self._get_tool_names()

        if name in current_tools:
            return

        mcp.add_tool(
            self._catalog[name],
            name=name,
        )

    def unregister(self, name: str) -> None:
        """Remove a tool from the MCP server."""

        if name in self._protected_tools:
            raise PermissionError(
                f"Protected tool cannot be removed: {name}"
            )

        if name not in self._catalog:
            raise KeyError(f"Unknown tool: {name}")

        current_tools = self._get_tool_names()

        if name not in current_tools:
            return

        mcp.remove_tool(name)

    def is_registered(self, name: str) -> bool:
        """Check whether a tool is currently exposed."""
        return name in self._get_tool_names()

    def list_registered(self) -> list[str]:
        """Return the currently exposed tool names."""
        return self._get_tool_names()

    def list_catalog(self) -> list[str]:
        """Return all tools known to the registry."""
        return sorted(self._catalog.keys())

    def _get_tool_names(self) -> set[str]:
        """
        Read the current tools directly from FastMCP.

        FastMCP.list_tools() is async, so for this first
        synchronous registry layer we inspect the underlying
        tool manager.
        """
        return {
            tool.name
            for tool in mcp._tool_manager.list_tools()
        }


tool_registry = ToolRegistry()