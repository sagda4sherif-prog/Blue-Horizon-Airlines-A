import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mcp_server.database import initialize_database
from mcp_server import tools
from mcp_server import resources
from mcp_server import prompts
from mcp_server.mcp_app import mcp


def start_server():
    initialize_database()

    transport = "stdio"

    if len(sys.argv) > 1:
        transport = sys.argv[1].lower()

    if transport == "http":
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
