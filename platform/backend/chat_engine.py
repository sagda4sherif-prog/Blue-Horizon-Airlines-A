"""
Backs the user-facing "chat with an agent" surface.

Two REAL agents today:

  "operations" — general MCP tool-calling loop. Opens one live stdio
  session against the actual mcp_server/server.py (same server the
  CLI agent/client.py talks to), lists whatever tools are CURRENTLY
  registered (so admin unregister/register decisions in routers/tools.py
  immediately change what this agent can do), and lets Claude call them
  to answer operational questions.

  "rag" — wraps rag/rag_pipeline.py's hybrid_search directly for
  policy/knowledge questions, then asks an LLM to answer from the
  retrieved chunks.

A third agent, "graph", talks to the three real LangGraph workflows in
state_graph/ (flight_recovery, flight_compensation, crew_reassignment).
It uses the same tool-calling pattern as "operations", except the
"tools" are this module's own wrappers around each graph's runner
function — so starting a run here is a real graph.invoke(), not a
simulation. See _run_graph_turn's docstring for what it can and can't
do yet (starting/checking runs: yes; resuming a paused run from a chat
turn: no — that's driven by the platform's HITL/ticket resolution
flow, per API_CONTRACT.md).
"""

import asyncio
import json
import sys

import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agent.mcp_tool_client import SERVER_SCRIPT_PATH

MODEL = "claude-sonnet-4-6"


def list_agents() -> list[dict]:
    return [
        {
            "id": "operations",
            "name": "Flight Operations Agent",
            "description": "Handles disruptions using the live MCP tool set.",
            "available": True,
        },
        {
            "id": "rag",
            "name": "Policy & Knowledge Agent",
            "description": "Answers questions from operational policy documents.",
            "available": True,
        },
        {
            "id": "graph",
            "name": "State-Graph Agents (AOG / Compensation / Crew)",
            "description": "Long-running, HITL-capable workflows.",
            "available": True,
        },
    ]


def _anthropic_client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


async def _run_operations_turn(history: list[dict]) -> str:
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[SERVER_SCRIPT_PATH],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tool_list = await session.list_tools()

            anthropic_tools = [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "input_schema": t.inputSchema,
                }
                for t in tool_list.tools
            ]

            client = _anthropic_client()
            messages = list(history)

            for _ in range(6):  # bounded tool-call loop
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=1024,
                    system=(
                        "You are Blue Horizon Airlines' flight operations "
                        "assistant. Use the available tools to look up "
                        "real data before answering. Never invent flight, "
                        "aircraft, or crew details."
                    ),
                    tools=anthropic_tools,
                    messages=messages,
                )

                if response.stop_reason != "tool_use":
                    return "".join(
                        block.text for block in response.content
                        if block.type == "text"
                    )

                messages.append({"role": "assistant", "content": response.content})

                tool_results = []

                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    result = await session.call_tool(
                        block.name, arguments=block.input
                    )

                    text_parts = [
                        item.text for item in (result.content or [])
                        if getattr(item, "text", None)
                    ]

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": "\n".join(text_parts) or "(no output)",
                        }
                    )

                messages.append({"role": "user", "content": tool_results})

            return (
                "I wasn't able to finish that within the tool-call budget "
                "for this turn — please rephrase or narrow the request."
            )


def run_operations_turn(history: list[dict]) -> str:
    return asyncio.run(_run_operations_turn(history))


def run_rag_turn(history: list[dict]) -> str:
    from rag.rag_pipeline import OperationalRAGPipeline

    pipeline = OperationalRAGPipeline()
    question = history[-1]["content"]

    if isinstance(question, list):
        question = "\n".join(
            b.get("text", "") for b in question if isinstance(b, dict)
        )

    chunks = pipeline.hybrid_search(question, top_k=4)

    client = _anthropic_client()

    response = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=(
            "Answer the operational-policy question using ONLY the "
            "provided excerpts. If they don't cover it, say so."
        ),
        messages=[
            {
                "role": "user",
                "content": (
                    f"Excerpts:\n{json.dumps(chunks, ensure_ascii=False)}\n\n"
                    f"Question: {question}"
                ),
            }
        ],
    )

    return "".join(b.text for b in response.content if b.type == "text")


_GRAPH_TOOLS = [
    {
        "name": "start_flight_recovery",
        "description": (
            "Start a flight-recovery workflow for an operational "
            "disruption (delay, cancellation, diversion). High-severity "
            "disruptions pause for admin approval before any recovery "
            "action is taken."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "flight_id": {"type": "integer"},
                "event_type": {
                    "type": "string",
                    "description": "e.g. 'delay', 'cancellation', 'diversion'",
                },
                "severity": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                },
                "description": {"type": "string"},
            },
            "required": ["flight_id", "event_type", "severity", "description"],
        },
    },
    {
        "name": "start_crew_reassignment",
        "description": (
            "Start a crew-reassignment workflow after a crew member "
            "becomes unavailable (illness, duty-hour limit). "
            "Reassignments that would leave the crew member within the "
            "duty-hour safety margin pause for admin approval."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "flight_id": {"type": "integer"},
                "crew_member_id": {"type": "integer"},
                "reason": {"type": "string"},
                "duty_hours_remaining": {"type": "number"},
                "candidate_crew": {
                    "type": "array",
                    "description": (
                        "Candidate replacement crew, e.g. "
                        "[{\"crew_id\": 99, \"name\": \"J. Rivera\"}]. "
                        "Pass an empty list if none are known yet."
                    ),
                    "items": {"type": "object"},
                },
            },
            "required": [
                "flight_id",
                "crew_member_id",
                "reason",
                "duty_hours_remaining",
                "candidate_crew",
            ],
        },
    },
    {
        "name": "start_flight_compensation",
        "description": (
            "Start a passenger-compensation workflow for a cancelled or "
            "significantly disrupted flight. Payouts above the policy "
            "threshold pause for admin approval before anything is paid."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "flight_id": {"type": "integer"},
                "passenger_id": {"type": "integer"},
                "cancellation_reason": {"type": "string"},
            },
            "required": ["flight_id", "passenger_id", "cancellation_reason"],
        },
    },
    {
        "name": "check_run_status",
        "description": (
            "Look up the latest checkpoint for a previously started "
            "run, by graph name and run_id, to see whether it's still "
            "running, waiting on an admin, completed, or failed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "graph_name": {
                    "type": "string",
                    "enum": [
                        "flight_recovery",
                        "crew_reassignment",
                        "flight_compensation",
                    ],
                },
                "run_id": {"type": "string"},
            },
            "required": ["graph_name", "run_id"],
        },
    },
]


def _call_graph_tool(name: str, tool_input: dict) -> dict:
    if name == "start_flight_recovery":
        from state_graph.flight_recovery.runner import run_flight_recovery

        return run_flight_recovery(
            flight_id=tool_input["flight_id"],
            event_type=tool_input["event_type"],
            severity=tool_input["severity"],
            description=tool_input["description"],
        )

    if name == "start_crew_reassignment":
        from state_graph.crew_reassignment.runner import run_crew_reassignment

        return run_crew_reassignment(
            flight_id=tool_input["flight_id"],
            crew_member_id=tool_input["crew_member_id"],
            reason=tool_input["reason"],
            duty_hours_remaining=tool_input["duty_hours_remaining"],
            candidate_crew=tool_input.get("candidate_crew") or [],
        )

    if name == "start_flight_compensation":
        from state_graph.flight_compensation.runner import run_flight_compensation

        return run_flight_compensation(
            flight_id=tool_input["flight_id"],
            passenger_id=tool_input["passenger_id"],
            cancellation_reason=tool_input["cancellation_reason"],
        )

    if name == "check_run_status":
        from state_graph.shared.checkpoint import load_latest_checkpoint

        checkpoint = load_latest_checkpoint(
            tool_input["graph_name"], tool_input["run_id"]
        )
        return checkpoint or {"error": "No checkpoint found for that run_id."}

    raise ValueError(f"Unknown graph tool: {name}")


def run_graph_turn(history: list[dict]) -> str:
    """Chat entrypoint for the "graph" agent. Each turn either starts a
    new state-graph run (a real graph.invoke() against
    flight_recovery/crew_reassignment/flight_compensation, which writes
    real checkpoints and, when a HITL/failure condition fires, a real
    row in HITLRequests/Tickets — see API_CONTRACT.md) or checks on one
    already started.

    What this does NOT do: resume a paused run from inside the chat. A
    run that pauses for HITL stays paused until an admin acts on it
    from /admin/hitl — that's the platform's job, not this chat loop's.
    This agent tells the user that plainly instead of pretending to
    have moved the run forward.
    """

    client = _anthropic_client()
    messages = list(history)

    for _ in range(6):  # bounded tool-call loop, same budget as "operations"
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=(
                "You are Blue Horizon Airlines' state-graph operations "
                "assistant. You can start three kinds of long-running "
                "workflows (flight recovery, crew reassignment, flight "
                "compensation) and check on ones already started. "
                "Ask for any required details you don't have before "
                "starting a run. After a run finishes or pauses, tell "
                "the user its run_id and status plainly. If a run's "
                "status is waiting_for_admin, tell the user it's "
                "sitting in the admin's HITL queue and will only "
                "resume once an admin acts on it there — you cannot "
                "approve it yourself from this chat. If a run's status "
                "is failed, tell them it opened a ticket for an admin "
                "to investigate."
            ),
            tools=_GRAPH_TOOLS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            return "".join(
                block.text for block in response.content if block.type == "text"
            )

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []

        for block in response.content:
            if block.type != "tool_use":
                continue

            try:
                result = _call_graph_tool(block.name, block.input)
                content = json.dumps(result, ensure_ascii=False, default=str)
            except Exception as e:  # noqa: BLE001 — surface to the model, not a 500
                content = json.dumps({"error": str(e)})

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": content,
                }
            )

        messages.append({"role": "user", "content": tool_results})

    return (
        "I wasn't able to finish that within the tool-call budget for "
        "this turn — please rephrase or narrow the request."
    )


def run_turn(agent_id: str, history: list[dict]) -> str:
    if agent_id == "operations":
        return run_operations_turn(history)

    if agent_id == "rag":
        return run_rag_turn(history)

    if agent_id == "graph":
        return run_graph_turn(history)

    raise ValueError(f"Unknown agent: {agent_id}")
