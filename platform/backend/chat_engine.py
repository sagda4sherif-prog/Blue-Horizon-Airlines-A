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

A third slot, "graph", is a placeholder: the three state-graph agents
(Persons 1/2/3's final deliverable) don't exist yet. list_agents()
reports it as unavailable rather than silently omitting it, so the
frontend can show it grayed out instead of pretending it was never
planned.
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
            "available": False,
            "unavailable_reason": (
                "state_graph/ has not been built yet — this slot will "
                "light up once Persons 1/2/3 deliver the three graphs."
            ),
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


def run_turn(agent_id: str, history: list[dict]) -> str:
    if agent_id == "operations":
        return run_operations_turn(history)

    if agent_id == "rag":
        return run_rag_turn(history)

    if agent_id == "graph":
        raise ValueError(
            "The state-graph agents aren't wired up yet — see "
            "platform/API_CONTRACT.md."
        )

    raise ValueError(f"Unknown agent: {agent_id}")
