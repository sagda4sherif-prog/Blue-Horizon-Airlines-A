"""
Launches the platform backend (FastAPI) on http://localhost:8001.

Why this exists instead of `uvicorn platform.backend.main:app`: the
folder is named `platform/` per the project brief, and Python already
has a stdlib module called `platform`. Importing this code as the
dotted package `platform.backend` would shadow that stdlib module for
every other library in the process that does `import platform`
(several do, for OS/arch checks) and cause hard-to-diagnose crashes.

This script sidesteps that by putting <repo_root>/platform — not
<repo_root> — on sys.path, so the backend loads as the top-level
package `backend`, never as `platform.backend`. <repo_root> is also
added so `mcp_server`, `agent`, and `rag` keep importing normally.

Usage:
    python run_platform_backend.py
"""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "platform"))

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8001, reload=True)
