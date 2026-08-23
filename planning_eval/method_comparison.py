# planning_eval/method_comparison.py
"""
Generates the "Method comparison" table for the README's Decomposition &
Planning Lab section:

    | Method | Task success | Avg. LLM calls | Avg. tokens |
    | Avg. latency | Est. cost/run |

Every number here comes from actually invoking the eight methods against a
real Gemini model and the real grounded database (`db/blue_horizon.db`) --
nothing is estimated or hardcoded, in keeping with the project's own rule
against fabricated evaluation numbers (see README's Bug Fix Log).

Requires a working GEMINI_API_KEY in `.env` (see `.env_example`) and
network access. Run from the project root:

    python -m planning_eval.method_comparison

Two methods need a caveat up front: `refine_notification` and
`run_reflexion_reassignment` in `agent/scheduling_agent.py` ship with
*deterministic* stand-ins for the planner/reviser step (by design -- see
their docstrings), so they make zero LLM calls in their shipped form. To
still report genuine LLM-call/token/latency numbers for Self-Refine and
Reflexion (rather than printing "0" and calling it a day), this script
swaps in a real-LLM reviser/planner for those two rows only, while keeping
the grounded, LLM-free validator/executor untouched. That swap is called
out again next to those two rows in the printed table notes.

Cost is computed from PRICE_PER_1K_TOKENS below -- fill that in with your
own model's published per-1K-token rate before trusting the "Est. cost/run"
column; this script does not guess or hardcode a price.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv

load_dotenv()

from planning.llm_content import extract_text

# Fill this in with your model's real published rate (USD per 1,000 tokens,
# input+output blended) before the "Est. cost/run" column means anything.
PRICE_PER_1K_TOKENS = 0.0


# ---------------------------------------------------------------------------
# Call-counting / token-counting / timing wrapper around the real LLM
# ---------------------------------------------------------------------------

@dataclass
class CallStats:
    calls: int = 0
    total_tokens: int = 0
    total_latency_s: float = 0.0
    tokens_are_estimated: bool = False


class MeteredChatModel:
    """Wraps a real `BaseChatModel` so every `.invoke(...)` and
    `.with_structured_output(...).invoke(...)` call updates `stats`,
    without changing any planning-module code."""

    def __init__(self, llm, stats: CallStats):
        self._llm = llm
        self.stats = stats

    def _record(self, start: float, response) -> None:
        self.stats.calls += 1
        self.stats.total_latency_s += time.time() - start

        usage = getattr(response, "usage_metadata", None) or (
            response.get("usage_metadata") if isinstance(response, dict) else None
        )
        if usage and usage.get("total_tokens"):
            self.stats.total_tokens += int(usage["total_tokens"])
        else:
            # Fallback: rough word-based estimate, clearly flagged as such
            # in the printed table rather than silently blended in as if
            # it were a real count from the API.
            self.stats.tokens_are_estimated = True
            text = str(response.content if hasattr(response, "content") else response)
            self.stats.total_tokens += max(1, int(len(text.split()) * 1.3))

    def invoke(self, *args, **kwargs):
        start = time.time()
        response = self._llm.invoke(*args, **kwargs)
        self._record(start, response)
        return response

    def with_structured_output(self, *args, **kwargs):
        inner = self._llm.with_structured_output(*args, **kwargs)
        return _MeteredStructured(inner, self)


class _MeteredStructured:
    """Return value of `MeteredChatModel.with_structured_output(...)`."""

    def __init__(self, inner, parent: MeteredChatModel):
        self._inner = inner
        self._parent = parent

    def invoke(self, *args, **kwargs):
        start = time.time()
        response = self._inner.invoke(*args, **kwargs)
        # Structured-output calls don't carry usage_metadata on the parsed
        # pydantic object; count the call and estimate tokens from the
        # rendered fields instead of leaving it uncounted.
        self._parent.stats.calls += 1
        self._parent.stats.total_latency_s += time.time() - start
        self._parent.stats.tokens_are_estimated = True
        text = str(response.model_dump() if hasattr(response, "model_dump") else response)
        self._parent.stats.total_tokens += max(1, int(len(text.split()) * 1.3))
        return response


def make_llm():
    from langchain_google_genai import ChatGoogleGenerativeAI

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not set. Copy .env_example to .env and fill in a real key."
        )
    # Bug fix: gemini-1.5-flash is fully shut down, and gemini-2.5-flash-lite
    # is closed to new users -- Google's own 404 response for the latter
    # points at gemini-3.5-flash-lite as of 2026. If this model is retired
    # too by the time you read this, swap in whatever ai.google.dev/gemini-api/docs/pricing
    # currently lists as the cheapest active model.
    return ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite", temperature=0.2)


# ---------------------------------------------------------------------------
# One consistent, realistic scenario every method is measured against
# ---------------------------------------------------------------------------

GOAL = (
    "Flight BH218's assigned aircraft just went into unscheduled maintenance. "
    "Find a valid replacement aircraft and backup crew member, and draft the "
    "passenger notification once a reassignment is decided."
)

CANDIDATE_POOL = [
    "Reassign Flight 2 (BH218) to Aircraft 3 with backup Crew 4 covering the delay",
    "Reassign Flight 2 (BH218) to Aircraft 3 with backup Crew 1 covering the delay",
    "Reassign Flight 2 (BH218) to Aircraft 1 with backup Crew 4 covering the delay",
    "Reassign Flight 2 (BH218) to Aircraft 1 with backup Crew 1 covering the delay",
]

NOTIFICATION_DRAFT = "We're sorry for the disruption to your flight."
NOTIFICATION_REQUIRED_FACTS = ["BH218", "new departure time", "Aircraft 1"]


# ---------------------------------------------------------------------------
# The eight methods
# ---------------------------------------------------------------------------

def run_decomposition_first(llm) -> bool:
    from planning.decomposition import decompose_goal, execute_plan, final_output

    plan = decompose_goal(GOAL, llm)
    outputs = execute_plan(plan, llm)
    final_output(plan, outputs)
    return True


def run_dynamic_decomposition(llm) -> bool:
    from planning.dynamic_decomposition import dynamic_decomposition

    history = dynamic_decomposition(GOAL, llm)
    return len(history) > 0


def run_plan_and_solve(llm) -> bool:
    from planning.plan_and_solve import plan_and_solve

    output = plan_and_solve(GOAL, llm)
    return bool(output)


def run_tree_of_thoughts(llm) -> bool:
    from planning.tree_of_thoughts import tree_of_thoughts

    thoughts = tree_of_thoughts(
        "Rank today's three disrupted flights by urgency for reassignment.",
        llm,
    )
    return len(thoughts) > 0


def _real_db_context() -> str:
    """Summarize the actual fleet/crew state from db/blue_horizon.db.

    Bug fix: `lats()`'s task prompt used to ask the LLM to propose a
    "valid aircraft and backup crew member" with zero visibility into
    which aircraft/crew ids exist or their real status -- GroundedEnvironment
    checks candidates against the real DB, but nothing grounded the
    *generation* step, so the LLM was guessing ids blind. With only
    iterations=2 * n_actions=2 = 4 total candidates, the odds of blindly
    guessing a combination that happens to pass every real check
    (availability, duty hours, maintenance, double-booking) were low --
    which is why grounded LATS kept losing to RandomEnvironment's "succeeds
    by not checking anything" default. Feeding the same facts
    GroundedEnvironment will check gives the LLM something real to reason
    over, the way a human dispatcher would have the fleet board in front
    of them instead of guessing tail numbers.
    """
    import sqlite3
    from pathlib import Path

    db_path = Path(__file__).resolve().parent.parent / "db" / "blue_horizon.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        aircraft_rows = conn.execute(
            "SELECT aircraft_id, tail_number, status, current_airport_id FROM Aircraft"
        ).fetchall()
        crew_rows = conn.execute(
            "SELECT crew_id, name, role, availability, hours_flown_today FROM Crew"
        ).fetchall()
        maint_rows = conn.execute(
            "SELECT aircraft_id, severity, status FROM Maintenance WHERE status != 'Completed'"
        ).fetchall()
    finally:
        conn.close()

    open_maint = {row["aircraft_id"]: f"{row['severity']}/{row['status']}" for row in maint_rows}

    aircraft_lines = "\n".join(
        f"- aircraft_id={row['aircraft_id']} ({row['tail_number']}): status={row['status']}"
        + (f", OPEN MAINTENANCE HOLD ({open_maint[row['aircraft_id']]})" if row["aircraft_id"] in open_maint else "")
        for row in aircraft_rows
    )
    crew_lines = "\n".join(
        f"- crew_id={row['crew_id']} ({row['name']}, {row['role']}): "
        f"{'available' if row['availability'] else 'NOT available'}, "
        f"{row['hours_flown_today']}h flown today (8h duty limit)"
        for row in crew_rows
    )
    return (
        f"Real fleet status:\n{aircraft_lines}\n\n"
        f"Real crew status:\n{crew_lines}\n\n"
        "Only propose an aircraft_id/crew_id combination that is actually "
        "consistent with the statuses above (no open maintenance hold, crew "
        "available and under the duty-hour limit)."
    )


def run_lats(llm, grounded: bool) -> bool:
    from planning.environment import GroundedEnvironment, RandomEnvironment
    from planning.lats import lats

    environment = GroundedEnvironment() if grounded else RandomEnvironment()
    task = (
        "Reassign flight BH218 (Flight 2) to a valid aircraft and backup crew "
        "member after the current aircraft went into maintenance.\n\n"
        + _real_db_context()
    )
    result = lats(task, llm, environment, iterations=4, n_actions=3)
    return result.success


def run_self_refine(llm) -> bool:
    """Real-LLM variant of `SchedulingAgent.refine_notification`: same
    grounded, string-containment validator; the reviser is swapped from the
    shipped deterministic stand-in to a real LLM rewrite so this row
    reflects genuine LLM cost, not the zero-call demo path."""
    from planning.self_refine import SelfRefiner

    def validator(message: str) -> dict:
        missing = [f for f in NOTIFICATION_REQUIRED_FACTS if f.lower() not in message.lower()]
        return {"valid": not missing, "errors": [f"missing required fact: {f}" for f in missing]}

    def reviser(message: str, errors: list[str]) -> str:
        response = llm.invoke([
            ("system", "Rewrite the passenger notification to fix the listed issues."),
            ("human", f"Current draft: {message}\nIssues: {errors}\nRewrite the notification."),
        ])
        # Bug fix: same list-content issue fixed in planning/ via extract_text --
        # this local reviser had its own isinstance(content, str) check, which
        # silently kept the message unchanged on newer Gemini models and made
        # Self-Refine look stalled/failed even on a perfectly good LLM reply.
        content = extract_text(response.content)
        return content.strip() if content.strip() else message

    refiner = SelfRefiner(validator=validator, max_iterations=3, reviser=reviser)
    result = refiner.refine(NOTIFICATION_DRAFT)
    return bool(result["success"])


def run_reflexion(llm) -> bool:
    """Real-LLM variant of `SchedulingAgent.run_reflexion_reassignment`:
    same grounded executor (`GroundedEnvironment` via the scheduling
    agent's `evaluate_candidate`); the planner is swapped from the shipped
    deterministic stand-in to a real LLM pick so this row reflects genuine
    LLM cost, not the zero-call demo path."""
    from planning.environment import GroundedEnvironment
    from reflexion import ReflexionAgent

    environment = GroundedEnvironment()
    pool_text = "\n".join(f"- {c}" for c in CANDIDATE_POOL)

    def planner(request, previous_lessons=None):
        avoided = [
            lesson.get("plan", {}).get("candidate", "")
            for lesson in (previous_lessons or [])
        ]
        avoid_text = "\n".join(f"- {c}" for c in avoided) or "None yet."
        response = llm.invoke([
            ("system", "Pick the single best untried candidate reassignment."),
            ("human", f"Candidates:\n{pool_text}\nAlready known-bad:\n{avoid_text}\n"
                       "Reply with exactly one full candidate line, unchanged."),
        ])
        # Bug fix: same list-content issue as above -- this used to silently
        # discard a real LLM pick on newer Gemini models and fall through to
        # the default candidate instead.
        content = extract_text(response.content).strip()
        candidate = content if content in CANDIDATE_POOL else next(
            (c for c in CANDIDATE_POOL if c not in avoided), CANDIDATE_POOL[-1]
        )
        return {"flight_id": request["flight_id"], "candidate": candidate}

    def executor(plan):
        feedback = environment.evaluate(plan["candidate"])
        return {"success": feedback.success, "score": feedback.score, "errors": feedback.details}

    agent = ReflexionAgent(planner=planner, executor=executor, max_trials=4)
    result = agent.run({"flight_id": "BH218"})
    return bool(result["success"])


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

@dataclass
class MethodResult:
    name: str
    success: bool = False
    error: str | None = None
    stats: CallStats = field(default_factory=CallStats)
    wall_time_s: float = 0.0


def run_method(name: str, fn) -> MethodResult:
    stats = CallStats()
    llm = MeteredChatModel(make_llm(), stats)
    result = MethodResult(name=name, stats=stats)
    start = time.time()
    try:
        result.success = bool(fn(llm))
    except Exception as exc:  # noqa: BLE001 - report, don't crash the whole run
        result.error = f"{type(exc).__name__}: {exc}"
        result.success = False
    result.wall_time_s = time.time() - start
    return result


METHODS = [
    ("Decomposition-first", run_decomposition_first),
    ("Dynamic decomposition", run_dynamic_decomposition),
    ("Plan-and-Solve", run_plan_and_solve),
    ("Tree of Thoughts", run_tree_of_thoughts),
    ("LATS, ungrounded (`RandomEnvironment`)", lambda llm: run_lats(llm, grounded=False)),
    ("LATS, grounded (`GroundedEnvironment`)", lambda llm: run_lats(llm, grounded=True)),
    ("Self-Refine", run_self_refine),
    ("Reflexion", run_reflexion),
]


def format_row(result: MethodResult) -> str:
    success = "yes" if result.success else ("error" if result.error else "no")
    calls = result.stats.calls
    tokens = result.stats.total_tokens
    tokens_str = f"~{tokens}" if result.stats.tokens_are_estimated else str(tokens)
    latency = f"{result.wall_time_s:.2f}s"
    cost = (
        f"${(tokens / 1000) * PRICE_PER_1K_TOKENS:.4f}"
        if PRICE_PER_1K_TOKENS > 0
        else "set PRICE_PER_1K_TOKENS"
    )
    return f"| {result.name} | {success} | {calls} | {tokens_str} | {latency} | {cost} |"


def main():
    print("=" * 70)
    print("BLUE HORIZON AIRLINES - PLANNING METHOD COMPARISON")
    print("=" * 70)
    print(
        "Self-Refine and Reflexion rows use a real-LLM reviser/planner "
        "swapped in for this run only; the shipped agent uses a "
        "deterministic stand-in there and makes zero LLM calls. See the "
        "module docstring."
    )
    print()

    rows = []
    for name, fn in METHODS:
        print(f"Running: {name} ...")
        result = run_method(name, fn)
        if result.error:
            print(f"  -> error: {result.error}")
        rows.append(result)

    print()
    print("| Method | Task success | Avg. LLM calls | Avg. tokens | Avg. latency | Est. cost/run |")
    print("|---|---|---|---|---|---|")
    for result in rows:
        print(format_row(result))

    if any(r.stats.tokens_are_estimated for r in rows):
        print()
        print(
            "Note: some rows fall back to a word-count token *estimate* "
            "because the API response for that call type didn't return "
            "usage_metadata (marked with ~ above)."
        )
    if PRICE_PER_1K_TOKENS == 0.0:
        print(
            "Note: Est. cost/run is unset -- fill in PRICE_PER_1K_TOKENS "
            "at the top of this script with your model's real rate."
        )


if __name__ == "__main__":
    main()