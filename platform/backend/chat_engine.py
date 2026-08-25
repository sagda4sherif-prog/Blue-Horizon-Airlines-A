"""
Blue Horizon Airlines - Chat Engine

Agents:
    operations
        Gemini + live MCP tools.

    rag
        Gemini + operational RAG pipeline.

    graph
        Gemini + real LangGraph workflows.

The operations agent uses the real MCP server and dynamically discovers
the currently registered MCP tools.
"""

import asyncio
import json
import os
import sys
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agent.mcp_tool_client import SERVER_SCRIPT_PATH


# ---------------------------------------------------------------------------
# Environment / Gemini
# ---------------------------------------------------------------------------

load_dotenv()

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")


def _gemini_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. "
            "Add GEMINI_API_KEY=... to the project's .env file."
        )

    return genai.Client(api_key=api_key)


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

def list_agents() -> list[dict]:
    return [
        {
            "id": "operations",
            "name": "Flight Operations Agent",
            "description": (
                "Handles disruptions using the live MCP tool set."
            ),
            "available": True,
        },
        {
            "id": "rag",
            "name": "Policy & Knowledge Agent",
            "description": (
                "Answers questions from operational policy documents."
            ),
            "available": True,
        },
        {
            "id": "graph",
            "name": "State-Graph Agents (AOG / Compensation / Crew)",
            "description": (
                "Long-running, HITL-capable workflows."
            ),
            "available": True,
        },
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_text(response: Any) -> str:
    """Safely extract text from a Gemini response."""

    text = getattr(response, "text", None)

    if text:
        return text

    parts = []

    candidates = getattr(response, "candidates", None) or []

    for candidate in candidates:
        content = getattr(candidate, "content", None)

        if not content:
            continue

        for part in getattr(content, "parts", None) or []:
            part_text = getattr(part, "text", None)

            if part_text:
                parts.append(part_text)

    return "".join(parts).strip()


def _response_content(response: Any) -> Any:
    """Return Gemini's generated Content object for tool-call continuation."""

    candidates = getattr(response, "candidates", None) or []

    if not candidates:
        return None

    return getattr(candidates[0], "content", None)


def _convert_history(history: list[dict]) -> list[types.Content]:
    """
    Convert API chat history into Gemini Content objects.

    The platform sends:
        {"role": "user", "content": "..."}
        {"role": "assistant", "content": "..."}
    """

    contents: list[types.Content] = []

    for message in history:
        role = message.get("role", "user")
        content = message.get("content", "")

        if isinstance(content, list):
            # Normally not used for the initial API history.
            text = "\n".join(
                str(item.get("text", ""))
                for item in content
                if isinstance(item, dict)
            )
        else:
            text = str(content)

        if not text.strip():
            continue

        # Gemini uses "user" and "model", not "assistant".
        gemini_role = "model" if role == "assistant" else "user"

        contents.append(
            types.Content(
                role=gemini_role,
                parts=[types.Part.from_text(text=text)],
            )
        )

    return contents


def _make_function_declaration(tool: Any) -> types.FunctionDeclaration:
    """
    Convert an MCP tool definition into a Gemini function declaration.
    """

    schema = tool.inputSchema or {
        "type": "object",
        "properties": {},
    }

    return types.FunctionDeclaration(
        name=tool.name,
        description=tool.description or "",
        parameters_json_schema=schema,
    )


# ---------------------------------------------------------------------------
# Operations Agent - Gemini + MCP
# ---------------------------------------------------------------------------

async def _run_operations_turn(history: list[dict]) -> str:
    """
    Run one operations-agent turn.

    Flow:

        User
          |
          v
        Gemini
          |
          | function call
          v
        MCP Client
          |
          v
        mcp_server/server.py
          |
          v
        Real MCP tool
          |
          v
        Tool result
          |
          v
        Gemini
          |
          v
        Final answer
    """

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[SERVER_SCRIPT_PATH],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:

            # ---------------------------------------------------------------
            # Initialize MCP
            # ---------------------------------------------------------------

            await session.initialize()

            tool_list = await session.list_tools()

            if not tool_list.tools:
                return (
                    "The operations MCP server is running, "
                    "but no tools are currently registered."
                )

            # ---------------------------------------------------------------
            # Convert MCP tools -> Gemini tools
            # ---------------------------------------------------------------

            function_declarations = [
                _make_function_declaration(tool)
                for tool in tool_list.tools
            ]

            gemini_tools = [
                types.Tool(
                    function_declarations=function_declarations
                )
            ]

            # ---------------------------------------------------------------
            # Gemini
            # ---------------------------------------------------------------

            client = _gemini_client()

            contents = _convert_history(history)

            if not contents:
                contents = [
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(
                                text="Hello."
                            )
                        ],
                    )
                ]

            system_instruction = (
                "You are Blue Horizon Airlines' Flight Operations Agent. "
                "You have access to live operational MCP tools. "
                "Use the tools to look up real data before answering "
                "questions about flights, aircraft, crew, maintenance, "
                "operations, notifications, or disruptions. "
                "Never invent flight, aircraft, passenger, crew, or "
                "operational details. "
                "If the available tools do not provide the requested "
                "information, clearly say that the information is "
                "unavailable. "
                "Do not claim that an operational action was completed "
                "unless the MCP tool actually returned a successful result."
            )

            # ---------------------------------------------------------------
            # Bounded tool-call loop
            # ---------------------------------------------------------------

            for _ in range(6):

                response = client.models.generate_content(
                    model=MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        tools=gemini_tools,
                        temperature=0,
                    ),
                )

                function_calls = getattr(response, "function_calls", None)

                # -----------------------------------------------------------
                # No function call -> final answer
                # -----------------------------------------------------------

                if not function_calls:
                    text = _extract_text(response)

                    return text or (
                        "I was unable to generate an operational response."
                    )

                # -----------------------------------------------------------
                # Preserve Gemini's tool-call message
                # -----------------------------------------------------------

                response_content = _response_content(response)

                if response_content is not None:
                    contents.append(response_content)

                # -----------------------------------------------------------
                # Execute MCP functions
                # -----------------------------------------------------------

                tool_response_parts = []

                for call in function_calls:

                    tool_name = getattr(call, "name", None)
                    tool_args = getattr(call, "args", None) or {}

                    if not tool_name:
                        continue

                    try:
                        result = await session.call_tool(
                            tool_name,
                            arguments=tool_args,
                        )

                        text_parts = []

                        for item in result.content or []:
                            item_text = getattr(item, "text", None)

                            if item_text:
                                text_parts.append(item_text)

                        result_text = (
                            "\n".join(text_parts)
                            if text_parts
                            else "(no output)"
                        )

                        tool_response_parts.append(
                            types.Part.from_function_response(
                                name=tool_name,
                                response={
                                    "result": result_text,
                                },
                            )
                        )

                    except Exception as exc:
                        tool_response_parts.append(
                            types.Part.from_function_response(
                                name=tool_name,
                                response={
                                    "error": str(exc),
                                },
                            )
                        )

                # -----------------------------------------------------------
                # Send MCP results back to Gemini
                # -----------------------------------------------------------

                if tool_response_parts:
                    contents.append(
                        types.Content(
                            role="user",
                            parts=tool_response_parts,
                        )
                    )

            return (
                "I wasn't able to finish the operational request within "
                "the tool-call limit. Please rephrase or narrow the request."
            )


def run_operations_turn(history: list[dict]) -> str:
    return asyncio.run(_run_operations_turn(history))


# ---------------------------------------------------------------------------
# RAG Agent - Gemini
# ---------------------------------------------------------------------------

def run_rag_turn(history: list[dict]) -> str:
    from rag.rag_pipeline import OperationalRAGPipeline

    if not history:
        return "Please provide a policy or operational question."

    question = history[-1].get("content", "")

    if isinstance(question, list):
        question = "\n".join(
            item.get("text", "")
            for item in question
            if isinstance(item, dict)
        )

    question = str(question).strip()

    if not question:
        return "Please provide a policy or operational question."

    pipeline = OperationalRAGPipeline()

    chunks = pipeline.hybrid_search(
        question,
        top_k=4,
    )

    client = _gemini_client()

    excerpts = json.dumps(
        chunks,
        ensure_ascii=False,
        default=str,
    )

    prompt = f"""
You are Blue Horizon Airlines' Policy & Knowledge Agent.

Answer the user's question using ONLY the operational-policy excerpts
provided below.

Rules:
- Do not invent policies.
- Do not use outside knowledge.
- If the excerpts do not contain enough information, explicitly say so.
- Give a concise and practical answer.

POLICY EXCERPTS:
{excerpts}

USER QUESTION:
{question}
"""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0,
        ),
    )

    return _extract_text(response) or (
        "I could not generate an answer from the available policy documents."
    )


# ---------------------------------------------------------------------------
# Graph tools
# ---------------------------------------------------------------------------

_GRAPH_TOOLS = [
    {
        "name": "start_flight_recovery",
        "description": (
            "Start a flight-recovery workflow for an operational "
            "disruption such as delay, cancellation, or diversion. "
            "High-severity disruptions may pause for admin approval."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "flight_id": {
                    "type": "integer",
                },
                "event_type": {
                    "type": "string",
                    "description": (
                        "For example: delay, cancellation, diversion."
                    ),
                },
                "severity": {
                    "type": "string",
                    "enum": [
                        "low",
                        "medium",
                        "high",
                    ],
                },
                "description": {
                    "type": "string",
                },
            },
            "required": [
                "flight_id",
                "event_type",
                "severity",
                "description",
            ],
        },
    },
    {
        "name": "start_crew_reassignment",
        "description": (
            "Start a crew-reassignment workflow after a crew member "
            "becomes unavailable."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "flight_id": {
                    "type": "integer",
                },
                "crew_member_id": {
                    "type": "integer",
                },
                "reason": {
                    "type": "string",
                },
                "duty_hours_remaining": {
                    "type": "number",
                },
                "candidate_crew": {
                    "type": "array",
                    "items": {
                        "type": "object",
                    },
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
            "Start a passenger-compensation workflow for a cancelled "
            "or significantly disrupted flight."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "flight_id": {
                    "type": "integer",
                },
                "passenger_id": {
                    "type": "integer",
                },
                "cancellation_reason": {
                    "type": "string",
                },
            },
            "required": [
                "flight_id",
                "passenger_id",
                "cancellation_reason",
            ],
        },
    },
    {
        "name": "check_run_status",
        "description": (
            "Look up the latest checkpoint for a previously started "
            "state-graph run."
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
                "run_id": {
                    "type": "string",
                },
            },
            "required": [
                "graph_name",
                "run_id",
            ],
        },
    },
]


# ---------------------------------------------------------------------------
# Graph execution
# ---------------------------------------------------------------------------

def _call_graph_tool(name: str, tool_input: dict) -> dict:

    if name == "start_flight_recovery":
        from state_graph.flight_recovery.runner import (
            run_flight_recovery,
        )

        return run_flight_recovery(
            flight_id=tool_input["flight_id"],
            event_type=tool_input["event_type"],
            severity=tool_input["severity"],
            description=tool_input["description"],
        )

    if name == "start_crew_reassignment":
        from state_graph.crew_reassignment.runner import (
            run_crew_reassignment,
        )

        return run_crew_reassignment(
            flight_id=tool_input["flight_id"],
            crew_member_id=tool_input["crew_member_id"],
            reason=tool_input["reason"],
            duty_hours_remaining=tool_input[
                "duty_hours_remaining"
            ],
            candidate_crew=tool_input.get(
                "candidate_crew"
            ) or [],
        )

    if name == "start_flight_compensation":
        from state_graph.flight_compensation.runner import (
            run_flight_compensation,
        )

        return run_flight_compensation(
            flight_id=tool_input["flight_id"],
            passenger_id=tool_input["passenger_id"],
            cancellation_reason=tool_input[
                "cancellation_reason"
            ],
        )

    if name == "check_run_status":
        from state_graph.shared.checkpoint import (
            load_latest_checkpoint,
        )

        checkpoint = load_latest_checkpoint(
            tool_input["graph_name"],
            tool_input["run_id"],
        )

        return checkpoint or {
            "error": "No checkpoint found for that run_id."
        }

    raise ValueError(f"Unknown graph tool: {name}")


# ---------------------------------------------------------------------------
# Graph Agent - Gemini
# ---------------------------------------------------------------------------

def run_graph_turn(history: list[dict]) -> str:

    client = _gemini_client()

    contents = _convert_history(history)

    if not contents:
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(
                        text="Hello."
                    )
                ],
            )
        ]

    function_declarations = [
        types.FunctionDeclaration(
            name=tool["name"],
            description=tool["description"],
            parameters_json_schema=tool["input_schema"],
        )
        for tool in _GRAPH_TOOLS
    ]

    gemini_tools = [
        types.Tool(
            function_declarations=function_declarations
        )
    ]

    system_instruction = (
        "You are Blue Horizon Airlines' State-Graph Operations Agent. "
        "You can start flight recovery, crew reassignment, and passenger "
        "compensation workflows, and check existing workflow status. "
        "Ask for required details before starting a workflow. "
        "After executing a workflow, report its run_id and status clearly. "
        "If a workflow is waiting_for_admin, explain that it is waiting "
        "in the admin HITL queue and cannot be approved from this chat. "
        "If a workflow fails, clearly report the failure."
    )

    for _ in range(6):

        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=gemini_tools,
                temperature=0,
            ),
        )

        function_calls = getattr(
            response,
            "function_calls",
            None,
        )

        if not function_calls:
            return _extract_text(response) or (
                "I was unable to generate a state-graph response."
            )

        response_content = _response_content(response)

        if response_content is not None:
            contents.append(response_content)

        tool_response_parts = []

        for call in function_calls:

            tool_name = getattr(call, "name", None)
            tool_input = getattr(call, "args", None) or {}

            if not tool_name:
                continue

            try:
                result = _call_graph_tool(
                    tool_name,
                    tool_input,
                )

                tool_output = {
                    "result": result,
                }

            except Exception as exc:
                tool_output = {
                    "error": str(exc),
                }

            tool_response_parts.append(
                types.Part.from_function_response(
                    name=tool_name,
                    response=tool_output,
                )
            )

        if tool_response_parts:
            contents.append(
                types.Content(
                    role="user",
                    parts=tool_response_parts,
                )
            )

    return (
        "I wasn't able to finish the state-graph request within "
        "the tool-call limit. Please rephrase or narrow the request."
    )


# ---------------------------------------------------------------------------
# Main router
# ---------------------------------------------------------------------------

def run_turn(
    agent_id: str,
    history: list[dict],
) -> str:

    if agent_id == "operations":
        return run_operations_turn(history)

    if agent_id == "rag":
        return run_rag_turn(history)

    if agent_id == "graph":
        return run_graph_turn(history)

    raise ValueError(
        f"Unknown agent: {agent_id}"
    )
