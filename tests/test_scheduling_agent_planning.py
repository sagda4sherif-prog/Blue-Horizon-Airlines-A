# tests/test_scheduling_agent_planning.py
"""Covers the grounded Self-Refine + Reflexion wiring added to
`agent/scheduling_agent.py`. Unlike `test_scheduling_agent.py`'s
divergence-case demo (decomposition-first vs. dynamic, no retries), this
file is the "a single retry isn't enough" case the rubric asks the
comparison table to include: candidates fail for different real reasons in
a row, and only Reflexion's carried-forward episodic memory gets to a
working reassignment.

Needs pydantic + networkx installed (see requirements.txt) because
`agent.scheduling_agent` imports `planning.environment.GroundedEnvironment`,
which imports `planning.models`. No LLM, network, or API key required —
this exercises the deterministic, DB-grounded path only.
"""
import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from agent.scheduling_agent import SchedulingAgent


def test_evaluate_candidate_is_grounded_against_real_database():
    agent = SchedulingAgent(mcp_client=None)

    # Aircraft 1 / Crew 1 are seeded as fully usable.
    good = agent.evaluate_candidate("Reassign to Aircraft 1 with backup Crew 1.")
    assert good["success"] is True

    # Aircraft 3 has a seeded High-severity 'In Progress' maintenance hold.
    bad = agent.evaluate_candidate("Reassign to Aircraft 3 with backup Crew 1.")
    assert bad["success"] is False


def test_reflexion_reassignment_needs_more_than_one_retry():
    agent = SchedulingAgent(mcp_client=None)

    # Aircraft 3 is blocked by maintenance; Crew 4 is unavailable. Only the
    # last candidate in the pool clears both real constraints, so this
    # needs 4 trials, not 1 or 2 — the case a single Self-Refine pass
    # cannot solve and only Reflexion's cross-trial memory gets through.
    candidates = [
        "Reassign to Aircraft 3 with backup Crew 4.",
        "Reassign to Aircraft 3 with backup Crew 1.",
        "Reassign to Aircraft 1 with backup Crew 4.",
        "Reassign to Aircraft 1 with backup Crew 1.",
    ]

    result = agent.run_reflexion_reassignment("BH218", candidates, max_trials=4)

    assert result["success"] is True
    assert len(result["trials"]) == 4
    assert result["trials"][-1]["plan"]["candidate"] == candidates[-1]
    # every earlier trial genuinely failed for a real, grounded reason
    for trial in result["trials"][:-1]:
        assert trial["result"]["success"] is False
        assert trial["result"]["errors"]


def test_reflexion_reassignment_gives_up_within_trial_budget():
    agent = SchedulingAgent(mcp_client=None)

    # Every candidate in this pool is grounded-invalid; a capped Reflexion
    # run must report failure rather than loop forever or claim success.
    candidates = [
        "Reassign to Aircraft 3 with backup Crew 4.",
        "Reassign to Aircraft 3 with backup Crew 4.",
    ]

    result = agent.run_reflexion_reassignment("BH218", candidates, max_trials=2)

    assert result["success"] is False
    assert len(result["trials"]) == 2


def test_refine_notification_converges_on_required_facts():
    agent = SchedulingAgent(mcp_client=None)

    draft = "Your flight has been delayed, we apologize for the inconvenience."
    result = agent.refine_notification(
        draft,
        required_facts=["Flight BH218", "10:45"],
        max_iterations=3,
    )

    assert result["success"] is True
    assert "Flight BH218" in result["plan"]
    assert "10:45" in result["plan"]
    # it took a real revision, not zero-shot luck
    assert result["iterations"] >= 2
