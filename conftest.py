"""
Ensures the project root is importable as a package root regardless of
how pytest is invoked (bare `pytest`, `python -m pytest`, or from a
subdirectory). Without this, running e.g. `pytest tests/test_planning_eval.py`
directly fails with `ModuleNotFoundError: No module named 'planning_eval'`
because pytest's default "prepend" import mode only adds the nearest
parent directory *without* an __init__.py (i.e. tests/ itself) to sys.path,
not the project root.
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)