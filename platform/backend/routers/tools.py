"""
Admin > Tool management.

REAL integration: talks directly to mcp_server.tool_registry.tool_registry,
the same singleton the running MCP server uses. Registering/unregistering
here calls mcp.add_tool()/mcp.remove_tool() under the hood, so a change
made from the admin panel reaches the live server immediately — no
redeploy, per the "Runtime Tool Registration" requirement.

Caveat worth knowing (not something this router can fix — it's Person
1's tool_registry/tools.py to address): tools defined with the
`@mcp.tool()` decorator in mcp_server/tools.py are registered directly
on import, ahead of and independent from tool_registry's own bookkeeping.
That only affects which tools start out registered, not whether
register()/unregister() work — both still act on the same live
FastMCP instance, so toggling here is still real.
"""

from fastapi import APIRouter, HTTPException

# Import triggers tools.py's module-level @mcp.tool() registrations
# and tool_registry.add_to_catalog(...) calls, exactly like starting
# the real server does.
import mcp_server.tools  # noqa: F401
from mcp_server.tool_registry import tool_registry

router = APIRouter(prefix="/api/admin/tools", tags=["admin:tools"])


@router.get("")
def list_tools():
    catalog = tool_registry.list_catalog()
    registered = set(tool_registry.list_registered())

    return {
        "tools": [
            {"name": name, "registered": name in registered}
            for name in catalog
        ]
    }


@router.post("/{tool_name}/register")
def register_tool(tool_name: str):
    try:
        tool_registry.register(tool_name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_name}")

    return {"name": tool_name, "registered": True}


@router.post("/{tool_name}/unregister")
def unregister_tool(tool_name: str):
    try:
        tool_registry.unregister(tool_name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_name}")
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    return {"name": tool_name, "registered": False}
