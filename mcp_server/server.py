import os
import sys

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from mcp_server.database import initialize_database
import mcp_server.import_tools
import mcp_server.import_resources
import mcp_server.import_prompts
from mcp_server.mcp_app import mcp


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
        mcp.run(
            transport="stdio"
        )


if __name__ == "__main__":
    start_server()
