"""Planning package for Blue Horizon Airlines.

Locatable concerns (see README "Decomposition & Planning Lab" section):

- DAG construction + acyclicity check: models.py (Plan.validate_dag)
- Decomposition-first:                 decomposition.py (decompose_goal, execute_plan)
- Dynamic/interleaved decomposition:   dynamic_decomposition.py (dynamic_decomposition)
- PS vs. ToT vs. LATS routing:         routing.py (PlanningRouter.choose_strategy / .run)
- Plan-and-Solve:                      plan_and_solve.py (plan_and_solve)
- Tree of Thoughts:                    tree_of_thoughts.py (tree_of_thoughts)
- LATS (MCTS + grounded feedback):     lats.py (lats)
- Grounded environment:                environment.py (GroundedEnvironment) vs.
                                        the ungrounded control (RandomEnvironment)
- Self-Refine:                         self_refine.py (SelfRefiner)
- Reflexion (episodic buffer):         ../reflexion.py (ReflexionAgent) — kept at
                                        repo root to match the reference toolkit's
                                        layout and existing test imports.
"""

# These two have zero third-party dependencies (pydantic + networkx only,
# both required by the whole repo) so they always import cleanly and are
# exposed unconditionally — including in environments that only want to
# run tests/test_environment.py or tests/test_*_models without the
# langchain/LLM stack installed.
from .environment import GroundedEnvironment, RandomEnvironment
from .models import EnvironmentFeedback, Plan, Task, Thought

__all__ = [
    "GroundedEnvironment",
    "RandomEnvironment",
    "EnvironmentFeedback",
    "Plan",
    "Task",
    "Thought",
]

# Everything below touches langchain_core.BaseChatModel. Import lazily/
# defensively so `import planning` (or importing just planning.environment)
# doesn't hard-fail in a slimmer environment that lacks the LLM stack —
# the same reason environment.py and models.py were split out above.
try:
    from .decomposition import decompose_goal, execute_plan, final_output
    from .dynamic_decomposition import dynamic_decomposition
    from .lats import lats
    from .plan_and_solve import plan_and_solve
    from .routing import PlanningRouter
    from .tree_of_thoughts import tree_of_thoughts

    __all__ += [
        "decompose_goal",
        "execute_plan",
        "final_output",
        "dynamic_decomposition",
        "lats",
        "plan_and_solve",
        "PlanningRouter",
        "tree_of_thoughts",
    ]
except ImportError:  # pragma: no cover - exercised only without langchain installed
    pass

# self_refine.py has no langchain dependency either, but is grouped with
# the algorithms above logically; import it unconditionally too.
from .self_refine import SelfRefiner, self_refine

__all__ += ["SelfRefiner", "self_refine"]
