import sys

from .database import initialize_database
from . import tools
from . import resources
from . import prompts
from .mcp_app import mcp


def start_server():
    initialize_database()

    transport = "stdio"

    if len(sys.argv) > 1:
        transport = sys.argv[1].lower()

    if transport == "http":
        print("Blue Horizon MCP Server is running on http://localhost:8000")

        mcp.run(
            transport="streamable-http",
            host="0.0.0.0",
            port=8000
        )

    else:
        print("Blue Horizon MCP Server is running using stdio")

        mcp.run(
            transport="stdio"
        )


if __name__ == "__main__":
    start_server()