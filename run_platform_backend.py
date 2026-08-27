"""
Run the Blue Horizon Airlines platform backend.
"""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "platform"))

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8001"))

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )
