import sys
from pathlib import Path


# Add the project root to Python path so `memory` is importable as a package.
sys.path.append(
    str(Path(__file__).resolve().parents[1])
)

from memory.manager import MemoryManager

# Re-export every test function from memory/test_memory.py so a single
# `pytest tests/` run covers both the low-level component tests and the
# integration tests below, instead of the low-level ones only being
# runnable from inside memory/.
from memory.test_memory import (  # noqa: F401
    test_short_term_memory,
    test_short_term_expiration,
    test_scratchpad,
    test_router_promotes_operational_event,
    test_router_drops_irrelevant_event,
    test_promoted_event_reaches_episodic_memory,
    test_consolidation_builds_semantic_memory,
    test_semantic_versioning,
    test_conflict_resolution,
    test_memory_expiration,
    test_full_memory_flow,
)


# ============================================================
# MemoryManager Integration Tests
# ============================================================
#
# Nothing previously exercised MemoryManager directly. These tests pin
# down the contract that matters most for the assignment: the
# promote-or-drop router must never write to semantic memory itself —
# only the separate, periodic consolidation pass may do that.

def test_manager_promote_does_not_touch_semantic_memory():
    manager = MemoryManager()

    result = manager.remember(
        "Flight BH218 was delayed",
        {"key": "BH218_status"}
    )

    assert result["action"] == "promote"
    assert len(manager.get_episodes()) == 1

    # Semantic memory must stay empty until consolidation runs separately.
    assert manager.recall("BH218_status") is None
    assert manager.get_semantic() == {}


def test_manager_drop_does_not_reach_episodic_memory():
    manager = MemoryManager()

    result = manager.remember("Hello, how are you?")

    assert result["action"] == "drop"
    assert manager.get_episodes() == []


def test_manager_consolidation_is_a_separate_call():
    manager = MemoryManager()

    manager.remember(
        "Flight BH218 was delayed",
        {"key": "BH218_status"}
    )

    # Still nothing in semantic memory before consolidation runs.
    assert manager.recall("BH218_status") is None

    consolidated_count = manager.run_consolidation()

    assert consolidated_count == 1
    assert manager.recall("BH218_status") == "Flight BH218 was delayed"


def test_manager_full_flow_with_conflicting_update():
    manager = MemoryManager()

    manager.remember(
        "Flight BH218 assigned Aircraft A",
        {"key": "BH218_aircraft"}
    )
    manager.run_consolidation()
    assert manager.recall("BH218_aircraft") == "Flight BH218 assigned Aircraft A"

    # A later, contradictory episode should supersede the earlier fact
    # once consolidation runs again, not silently disappear.
    manager.remember(
        "Flight BH218 assigned Aircraft B",
        {"key": "BH218_aircraft"}
    )
    manager.run_consolidation()

    assert manager.recall("BH218_aircraft") == "Flight BH218 assigned Aircraft B"


if __name__ == "__main__":
    import inspect

    module = sys.modules[__name__]
    test_functions = [
        (name, obj)
        for name, obj in inspect.getmembers(module)
        if name.startswith("test_") and inspect.isfunction(obj)
    ]

    passed, failed = 0, 0

    for name, func in test_functions:
        try:
            func()
            print(f"PASS: {name}")
            passed += 1
        except Exception as exc:
            print(f"FAIL: {name} -> {type(exc).__name__}: {exc}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")

    if failed:
        sys.exit(1)
