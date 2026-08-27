"""
Run the Blue Horizon Airlines platform backend.
"""

import os
import sys
import threading
import time
import webbrowser

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "platform"))


def open_backend():
    time.sleep(2)
    webbrowser.open("http://localhost:8001/docs")


if __name__ == "__main__":
    import uvicorn

    print()
    print("=" * 60)
    print("Blue Horizon Airlines Platform Backend")
    print()
    print("OPEN THIS LINK:")
    print("http://localhost:8001")
    print()
    print("API Health:")
    print("http://localhost:8001/api/health")
    print()
    print("Swagger:")
    print("http://localhost:8001/docs")
    print("=" * 60)
    print()

    threading.Thread(target=open_backend, daemon=True).start()

    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8001,
        reload=True,
    )
