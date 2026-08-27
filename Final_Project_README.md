# Blue Horizon Airlines — Final Project

Blue Horizon Airlines is an integrated AI-powered Flight Operations platform that combines a mediated MCP server, persistent memory, RAG-based operational knowledge, decomposition and planning, state-graph workflows, and a web platform for real operational interaction.

The project is built as one connected system rather than separate demonstrations. The web platform exposes the underlying agents and workflows to real users and administrators while preserving the authorization, validation, persistence, and human-in-the-loop boundaries implemented in the underlying system.

---

## System Architecture

```text
                         ┌──────────────────────────┐
                         │     Next.js Frontend     │
                         │                          │
                         │  User Chat │ Admin UI   │
                         └────────────┬─────────────┘
                                      │
                                      ▼
                         ┌──────────────────────────┐
                         │      FastAPI Backend     │
                         │                          │
                         │ Chat │ RAG │ Tools │ HITL│
                         │        Graph Bridge     │
                         └──────┬──────┬──────┬─────┘
                                │      │      │
                    ┌───────────┘      │      └───────────┐
                    ▼                  ▼                  ▼
             ┌────────────┐    ┌────────────┐    ┌──────────────┐
             │ MCP Server │    │ RAG /      │    │ State Graphs │
             │            │    │ Memory     │    │              │
             │ Tools      │    │            │    │ Recovery     │
             │ Resources  │    │ Hybrid RAG │    │ Compensation │
             │ Prompts    │    │ Memory     │    │ Crew         │
             │ Auth/HITL  │    │ Context    │    │ Reassignment │
             └─────┬──────┘    └────────────┘    └──────┬───────┘
                   │                                     │
                   └────────────────┬────────────────────┘
                                    ▼
                           ┌─────────────────┐
                           │ SQLite Database │
                           │                 │
                           │ Flights         │
                           │ Aircraft        │
                           │ Crew            │
                           │ Maintenance     │
                           │ Tickets / HITL  │
                           │ Audit records   │
                           └─────────────────┘
```

---

# 1. MCP Server Lab

The MCP server provides the controlled operational interface to the Blue Horizon Airlines database.

It exposes:

* operational tools
* read-only resources
* reusable prompts
* authentication and authorization
* notifications
* elicitation for high-risk actions
* sampling for independent risk assessment
* progress reporting
* defensive server-side validation

Write operations are never treated as unrestricted database access.

State-changing operations validate authorization and operational constraints at the server boundary.

### High-risk cancellation

Flight cancellation is explicitly protected by human elicitation.

The cancellation flow is:

```text
User request
     ↓
Authorization check
     ↓
Operational validation
     ↓
Human confirmation / elicitation
     ↓
Database commit
     ↓
Audit record
```

If the connected MCP client does not support elicitation, the server returns a clear error instead of silently cancelling or hanging.

### Transport

The MCP server supports:

* stdio for development and the graded demo
* Streamable HTTP for connected deployments

```bash
python mcp_server/server.py
```

or:

```bash
python mcp_server/server.py http
```

---

# 2. Memory & RAG Lab

The Memory and RAG system solves two operational problems:

1. preserving important information across sessions
2. retrieving operational policies without converting the policy manual into dozens of tools

## Memory

The memory architecture contains:

* Short-term memory
* Scratchpad
* Promote-or-drop routing
* Episodic memory
* Semantic memory
* Consolidation
* Conflict resolution
* Versioning
* Expiration
* Memory orchestration

Semantic consolidation is intentionally separate from event routing.

The router only promotes operationally relevant information to episodic memory. A separate consolidation pass creates or updates semantic facts.

This prevents every incoming message from automatically overwriting long-term knowledge.

## RAG

The operational policy manual is processed into chunks and indexed in Chroma using local embeddings.

Three retrieval strategies are implemented:

* Naive RAG
* Hybrid Search
* Agentic RAG

Self-RAG-style verification is applied after retrieval to verify that retrieved context is relevant and sufficient before it is used to support an answer.

### Retrieval evaluation

The evaluation covers:

* general policy questions
* citation-heavy questions
* multi-part operational questions

Hybrid search is particularly useful for exact policy identifiers, while Agentic RAG is useful for questions requiring multiple retrieval steps.

---

# 3. Long-Context Management

The Operations Agent includes four context-management strategies:

1. Sliding Window
2. Observation and Tool-Output Masking
3. Recursive Summarization
4. Zone-Based Pruning

The evaluated scenarios include:

* weather delay
* maintenance issue
* crew reassignment
* flight cancellation

Observation Masking was selected as the best overall strategy because it preserved the required operational information while reducing tool-output noise with low latency.

---

# 4. Decomposition & Planning Lab

The Scheduling Agent handles disruption scenarios where selecting the first available option is not sufficient.

The planning system includes:

* DAG validation
* decomposition-first planning
* dynamic/interleaved decomposition
* Plan-and-Solve
* Tree of Thoughts
* grounded LATS
* Planning Router
* Self-Refine
* Reflexion
* grounded environment evaluation

The planning environment is connected to the real SQLite operational database.

It checks:

* aircraft status
* maintenance holds
* aircraft scheduling conflicts
* crew availability
* crew duty-hour limits
* flight assignment constraints

The old randomized environment is retained only as an explicit ungrounded control for evaluation.

---

# 5. State-Graph Workflows

The platform integrates long-running workflows that require persistence, failure handling, and human approval.

Implemented workflows include:

* Flight Recovery
* Flight Compensation
* Crew Reassignment

These workflows are designed for situations where a normal function call is insufficient because the process may:

* pause for human approval
* fail after partial progress
* resume from persisted state
* create operational tickets
* require an administrator to resolve an issue

The platform does not fake this state.

The FastAPI backend exposes the state-graph runs through a graph bridge, while the underlying workflows remain responsible for their own execution and checkpoint/resume behavior.

---

# 6. Web Platform

The web platform is the user-facing layer of the complete system.

It consists of:

```text
platform/
├── backend/
│   ├── main.py
│   ├── chat_engine.py
│   ├── graph_bridge.py
│   └── routers/
│       ├── chat.py
│       ├── rag.py
│       ├── tools.py
│       ├── tickets.py
│       └── hitl.py
│
└── frontend/
    ├── app/
    │   ├── page.tsx
    │   └── admin/
    │       ├── page.tsx
    │       ├── tools/
    │       ├── rag/
    │       ├── tickets/
    │       └── hitl/
    └── lib/
        └── api.ts
```

## Backend

The FastAPI backend is a bridge rather than a replacement implementation.

It communicates with:

* the real MCP tool registry
* the real RAG pipeline
* the state-graph workflows
* the SQLite-backed operational system
* the chat agents

The backend exposes the platform API on port `8001`.

Because the repository contains a folder named `platform/`, the backend should be started through:

```bash
python run_platform_backend.py
```

rather than:

```bash
uvicorn platform.backend.main:app
```

The launcher avoids the collision between the project `platform/` package name and Python's standard-library `platform` module.

---

# 7. User Chat

The root page provides the main user-facing chat interface.

Users can switch between the available agents rather than interacting with a single hardcoded chatbot.

The currently integrated agent surfaces include:

### Operations Agent

Handles live operational requests using the MCP tool layer.

Examples:

* flight status
* aircraft availability
* crew availability
* operational disruptions
* controlled operational actions

### RAG / Policy Agent

Answers questions against the operational knowledge base.

Examples:

* crew-duty rules
* weather-delay procedures
* maintenance policy
* operational requirements

### Graph Agent

Starts and monitors state-graph workflows.

Supported workflow families include:

* flight recovery
* crew reassignment
* flight compensation

A graph run that pauses for HITL is not falsely resumed by the chat agent. The admin surface is responsible for the human decision, after which the underlying workflow can continue through its own state-management mechanism.

---

# 8. Admin Dashboard

The `/admin` surface provides operational administration.

It includes:

* Overview
* MCP Tool Management
* RAG Document Management
* Tickets
* HITL Requests

## Tool Management

Administrators can inspect the tools available through the MCP system and register/unregister tools through the platform.

This is connected to the live tool registry rather than being a static UI configuration.

## RAG Management

Administrators can add and remove documents from the RAG system.

Changes are propagated to the retrieval pipeline so that subsequent queries use the updated knowledge source.

## Tickets

Operational failures and issues created by the state-graph workflows appear in the ticket queue.

Administrators can inspect and resolve open tickets.

## HITL

High-impact workflows can create pending human-approval requests.

Administrators can inspect the request and its workflow context and provide the required decision.

---

# 9. API Contract

`platform/API_CONTRACT.md` defines the interface between the platform and the state-graph layer.

The contract covers the information required for:

* creating tickets
* creating HITL requests
* retrieving workflow state
* resolving tickets
* resolving HITL decisions
* allowing the underlying workflow to continue

This keeps the platform independent from the internal implementation details of each state graph.

---

# 10. End-to-End Flow

A typical operational request can pass through the entire system:

```text
User
 ↓
Next.js Chat
 ↓
FastAPI
 ↓
Agent Router
 ↓
Operations / RAG / Graph Agent
 ↓
 ┌───────────────┬────────────────┬─────────────────┐
 │               │                │
 ▼               ▼                ▼
MCP Tools       RAG            State Graph
 │               │                │
 ▼               ▼                ▼
Database       Chroma          Checkpoint State
 │                                │
 └───────────────┬────────────────┘
                 ▼
          Ticket / HITL
                 │
                 ▼
          Admin Dashboard
                 │
                 ▼
       Human Decision / Resolution
                 │
                 ▼
        Workflow Continues
```

This is the main integration point between all project labs.

---

# 11. What's Real

| Feature                             | Status   |
| ----------------------------------- | -------- |
| MCP operational tools               | **Real** |
| MCP resources                       | **Real** |
| MCP prompts                         | **Real** |
| MCP authorization                   | **Real** |
| MCP cancellation elicitation        | **Real** |
| MCP sampling risk assessment        | **Real** |
| Persistent memory                   | **Real** |
| Memory consolidation                | **Real** |
| Memory versioning/conflict handling | **Real** |
| Naive RAG                           | **Real** |
| Hybrid RAG                          | **Real** |
| Agentic RAG                         | **Real** |
| Self-RAG verification               | **Real** |
| Context management                  | **Real** |
| Grounded planning environment       | **Real** |
| Plan-and-Solve                      | **Real** |
| Tree of Thoughts                    | **Real** |
| Grounded LATS                       | **Real** |
| Self-Refine                         | **Real** |
| Reflexion                           | **Real** |
| Flight Recovery graph               | **Real** |
| Flight Compensation graph           | **Real** |
| Crew Reassignment graph             | **Real** |
| User chat                           | **Real** |
| Agent switching                     | **Real** |
| Admin dashboard                     | **Real** |
| MCP tool management                 | **Real** |
| RAG document management             | **Real** |
| Tickets                             | **Real** |
| HITL queue                          | **Real** |
| Graph-to-platform integration       | **Real** |

---

# 12. Known Limitations

The project intentionally documents several limitations rather than presenting unsupported functionality as complete.

### RAG

Metadata-based pre-filtering and Graph RAG are not implemented because the current operational-policy corpus does not contain the relational structure that would justify Graph RAG.

### Planning Evaluation

The complete LLM-backed planning comparison requires a live Gemini API key and network access.

The evaluation harness is provided so the final metrics can be generated from actual runs rather than fabricated values.

### State-Graph Resume

The platform surfaces paused workflows and human decisions, but the actual checkpoint and resume mechanics belong to the state-graph implementation.

The chat interface does not pretend that a paused graph has completed when an administrator has not yet supplied the required decision.

---

# 13. Running the Complete Project

## 13.1 Install dependencies

From the repository root:

```bash
pip install -r requirements.txt
```

Configure `.env`:

```text
GEMINI_API_KEY=your-key
```

Add any provider-specific key required by the configured chat agent.

Never commit `.env`.

---

## 13.2 Initialize the database

```bash
python mcp_server/database.py
```

---

## 13.3 Run the Platform Backend

From the repository root:

```bash
python run_platform_backend.py
```

Backend:

```text
http://localhost:8001
```

Health check:

```text
http://localhost:8001/api/health
```

Agents:

```text
http://localhost:8001/api/agents
```

---

## 13.4 Run the Frontend

In another terminal:

```bash
cd platform/frontend
npm install
npm run dev
```

Frontend:

```text
http://localhost:3000
```

Main routes:

```text
/          → User Chat
/admin     → Admin Dashboard
```

The Next.js development configuration proxies API requests to the FastAPI backend, so a separate CORS configuration is not required for local development.

---

# 14. MCP Standalone Demo

The MCP server can also be tested independently of the web platform.

```bash
python mcp_server/server.py
```

Then:

```bash
python agent/client.py
```

For Streamable HTTP:

```bash
python mcp_server/server.py http
```

---

# 15. Testing

### Memory

```bash
pytest tests/test_memory.py -v
```

### Context Management

```bash
pytest tests/test_context.py -v
```

### Grounded Environment

```bash
pytest tests/test_environment.py -v
```

### Scheduling Agent

```bash
pytest tests/test_scheduling_agent.py -v
pytest tests/test_scheduling_agent_planning.py -v
```

### Self-Refine / Reflexion

```bash
pytest tests/test_self_refine.py tests/test_reflexion.py -v
```

### Planning Integration

```bash
pytest tests/test_planning_integration.py -v
```

### Full Planning Evaluation

Requires a live Gemini API connection:

```bash
python -m planning_eval.runner
```

---

# 16. Evaluation Evidence

Evaluation outputs are stored under:

```text
artifacts/
```

The planning evaluation produces:

```text
artifacts/planning_results.json
```

The evaluation scripts should be run against the live environment before submission so that reported latency, token usage, and task-success measurements represent actual runs.

---

# 17. Project Structure

```text
Blue-Horizon-Airlines-A/
│
├── db/
│   ├── schema.sql
│   └── seed.sql
│
├── mcp_server/
│   ├── server.py
│   ├── tools.py
│   ├── resources.py
│   ├── prompts.py
│   ├── notifications.py
│   ├── elicitation.py
│   └── database.py
│
├── agent/
│   ├── client.py
│   ├── context_manager.py
│   └── scheduling_agent.py
│
├── memory/
│   ├── short_term.py
│   ├── scratchpad.py
│   ├── router.py
│   ├── episodic.py
│   ├── semantic.py
│   ├── consolidation.py
│   ├── conflict_resolution.py
│   ├── versioning.py
│   ├── expiration.py
│   └── manager.py
│
├── rag/
│   ├── rag_pipeline.py
│   ├── rag_data/
│   └── vector_db/
│
├── planning/
│   ├── models.py
│   ├── decomposition.py
│   ├── dynamic_decomposition.py
│   ├── plan_and_solve.py
│   ├── tree_of_thoughts.py
│   ├── lats.py
│   ├── routing.py
│   ├── self_refine.py
│   └── environment.py
│
├── planning_eval/
│   ├── scenarios.py
│   ├── runner.py
│   ├── adapter.py
│   └── metrics.py
│
├── state_graph/
│   ├── flight_recovery/
│   ├── flight_compensation/
│   └── crew_reassignment/
│
├── platform/
│   ├── backend/
│   │   ├── main.py
│   │   ├── chat_engine.py
│   │   ├── graph_bridge.py
│   │   └── routers/
│   │
│   └── frontend/
│       ├── app/
│       │   ├── page.tsx
│       │   └── admin/
│       └── lib/
│
├── evaluation/
│   ├── eval.py
│   └── context_evaluation.py
│
├── tests/
│
├── artifacts/
│
├── reflexion.py
├── run_platform_backend.py
├── requirements.txt
└── README.md
```

---

# 18. Team Ownership

## MCP Server / Database / Memory / RAG

| Owner    | Responsibility                    |
| -------- | --------------------------------- |
| Person 1 | Database and Memory               |
| Person 2 | MCP Server and Context Management |
| Person 3 | Agent integration and RAG         |
| Person 4 | Web Platform                      |

## Planning Lab

| Owner                                  | Responsibility                                  |
| -------------------------------------- | ----------------------------------------------- |
| Dalia Hossam                           | DAG, decomposition, dynamic decomposition       |
| Dalia Hossam, Somia Ahmed              | Plan-and-Solve, Tree of Thoughts, LATS, routing |
| Dalia Hossam, Somia Ahmed, Sama Sherif | Self-Refine, Reflexion, grounded environment    |
| Dalia Hossam, Sama Sherif              | Planning evaluation                             |
| Dalia Hossam                           | Scheduling Agent and live integration           |

---

# 19. Final Integration Goal

The final system is not a collection of isolated labs.

The intended architecture is:

```text
                    BLUE HORIZON AIRLINES
                       OPERATIONS AI
                              │
              ┌───────────────┼───────────────┐
              │               │               │
          Operations        Policy          Planning
             Agent           Agent            Agent
              │               │               │
             MCP             RAG          Scheduling
              │               │               │
              └───────────────┼───────────────┘
                              │
                       State Graphs
                              │
                    ┌─────────┴─────────┐
                    │                   │
                  Tickets             HITL
                    │                   │
                    └─────────┬─────────┘
                              │
                       Admin Dashboard
                              │
                         Human Control
```

The web platform provides the common interface, while each underlying component remains responsible for its own domain:

* MCP controls operational capabilities and authorization.
* RAG controls policy retrieval and verification.
* Memory preserves operational context.
* Planning handles branching decisions.
* State graphs handle long-running workflows and recovery.
* The platform connects users and administrators to those systems.
* Human approval remains the final control point for high-impact operations.

The project therefore demonstrates an end-to-end operational AI system rather than a standalone chatbot.
