# Project Management Orchestration

An AI-powered project management dashboard with a **human-in-the-loop agent** that
reads any public GitHub repository, analyzes its source code, and generates a
ready-to-work project plan — tasks, milestones, tech stack, and documentation —
which appears live in the dashboard.

Built with **LangChain + LangGraph** for the agent runtime, **FastAPI** + **React/TypeScript**
for the application layer, the **Model Context Protocol (MCP)** for extensible tool
integration, and an audit subsystem modeled on **NIST 800-53 / FedRAMP** controls.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-0.3-1C3C3C?logo=langchain&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-0.3-FF6F00)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-5-646CFF?logo=vite&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini-2.5%20Flash-8E75B2?logo=google&logoColor=white)
![MCP](https://img.shields.io/badge/MCP-stdio-000000)
![Tests](https://img.shields.io/badge/tests-pytest%20%2B%20vitest-0A9EDC)
![TDD](https://img.shields.io/badge/development-TDD-success)

---

## What it does

Paste a GitHub URL into the chat panel. The agent will:

1. Call `read_github_repo` to fetch metadata, languages, README, contributors, open issues, and the file tree.
2. Pick 2–4 key files (entry points, manifests, core modules) and call `read_repo_file` to read the actual source.
3. Synthesize a project: name, description, tech stack, 3–6 prioritized tasks, 2–4 milestones, and a documentation summary.
4. Call `create_project` — the new project appears live on your dashboard with a kanban board, milestones, and contributor avatars.

Every tool call **pauses** for explicit Approve / Deny in the UI before it runs.

---

## Highlights

| Area | What's interesting |
|---|---|
| **Agent architecture** | LangGraph `create_react_agent` with `MemorySaver` checkpointer and `interrupt_before=["tools"]` — gives a true pause-resume loop, not a one-shot prompt. |
| **Human-in-the-loop** | Each tool call surfaces an Approve / Deny card. Denial injects synthetic `ToolMessage`s so the LLM sees the refusal and adapts its next step. |
| **MCP integration** | `tools/mcp_langchain.py` auto-discovers tools from any MCP stdio server and wraps them as LangChain `StructuredTool`s with full JSON Schema validation. |
| **Auditability** | Every LLM event passes through `AuditCallbackHandler` → append-only JSONL with NIST 800-53 event types, UTC timestamps, and regex-based secret scrubbing. |
| **TDD discipline** | Red-Green-Refactor is the project's enforced workflow — pytest + vitest, with tests committed alongside every feature. |
| **No backend lock-in** | Storage is a flat SQLite/JSON file. The agent layer is provider-agnostic — swap `ChatGoogleGenerativeAI` for any LangChain chat model in one line. |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  React + TypeScript (Vite, :5173)                                   │
│                                                                     │
│   ProjectDashboard ── ProjectCard ── ProjectDetail ── TaskBoard     │
│         │                                              MilestoneList│
│         └── ChatPanel ── ToolApprovalCard ── ToolStepCard           │
└──────────────┬──────────────────────────────────────────────────────┘
               │  /api/chat, /api/chat/approve, /api/chat/deny
               │  /api/projects, /api/projects/from-github, /api/logs
               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  FastAPI (:8000)                                                    │
│                                                                     │
│   Thread registry  →  ThreadPoolExecutor  →  LangGraph agent        │
│                                                                     │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  LangGraph create_react_agent                               │   │
│   │    model: ChatGoogleGenerativeAI(gemini-2.5-flash)          │   │
│   │    checkpointer: MemorySaver                                │   │
│   │    interrupt_before: ["tools"]   ◄── HITL pause point       │   │
│   │                                                             │   │
│   │    Tools:                                                   │   │
│   │      @tool read_github_repo                                 │   │
│   │      @tool read_repo_file                                   │   │
│   │      @tool create_project                                   │   │
│   │      + MCP tools (auto-wrapped via mcp_langchain.py)        │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│   AuditCallbackHandler  →  append-only JSONL  (NIST 800-53)         │
│   SecretScrubber        →  redaction before write                   │
└─────────────────────────────────────────────────────────────────────┘
```

### Step-by-step tool approval

The non-obvious piece. A plain ReAct loop runs LLM → tool → LLM → tool → … to completion.
For a "real" project management workflow, the user needs to see and approve each tool call.

This is implemented by composing two LangGraph features:

- **`MemorySaver` checkpointer** — persists graph state per `thread_id`, so the run can be paused and resumed across HTTP requests.
- **`interrupt_before=["tools"]`** — the graph halts *before* the tools node executes.

The flow:

```
POST /api/chat          ──►  agent.invoke()
                              graph runs until interrupt
                              ChatStepResponse(status="tool_pending", pending_tools=[…])

POST /api/chat/approve  ──►  agent.invoke(None)        # resumes from checkpoint
                              tools execute, graph runs to next interrupt or completion

POST /api/chat/deny     ──►  agent.update_state(…, ToolMessage(content=reason))
                              agent.invoke(None)
                              the LLM sees the denial and replans
```

The thread ID lives in an in-memory registry with a 1-hour TTL.

### Audit subsystem

`AuditCallbackHandler` is a `BaseCallbackHandler` subclass plugged into the LangChain
runtime. It maps lifecycle events to a controlled vocabulary of audit event types:

| LangChain event | Audit event | NIST control |
|---|---|---|
| `on_tool_start` | `TOOL_CALL_PROPOSED` | AU-2, AU-12 |
| `on_tool_end` | `TOOL_EXECUTED` | AU-2, AU-12 |
| `on_tool_error` | `TOOL_BLOCKED` | SI-3, SI-10 |
| `on_llm_start` | `AGENT_TASK_START` | AU-2 |
| `on_llm_end` | `AGENT_TASK_END` | AU-2 |

Every record carries `session_id`, ISO-8601 UTC timestamp, scrubbed tool args, and a
truncated result summary. Writes are synchronous + flushed (`AU-12`), append-only
(`AU-9`), and the secret scrubber redacts API keys / bearer tokens / PEM blocks before
any value lands on disk (`SC-28`).

---

## Tech stack

**Backend** — Python 3.10+, FastAPI, LangChain Core, LangGraph, langchain-google-genai (Gemini 2.5 Flash), MCP (stdio), httpx, Pydantic, SQLite/JSON storage.

**Frontend** — React 18, TypeScript, Vite 5, React Router, Tailwind CSS, Vitest, Testing Library.

**Testing** — pytest + pytest-asyncio for the Python layer; Vitest + jsdom + Testing Library for the React layer. TDD is enforced — see `CLAUDE.md`.

---

## Repository layout

```
.
├── agents/
│   └── project_creator.py        Pure-Python agent (system prompt + build_agent)
├── api/
│   ├── server.py                 FastAPI: chat, approve/deny, projects, logs
│   ├── storage.py                SQLite-backed project storage
│   └── models.py                 Pydantic request/response models
├── framework/
│   ├── audit_logger.py           Append-only JSONL audit log
│   ├── secret_scrubber.py        Regex redaction (AU-9 / SC-28)
│   ├── mcp_client.py             MCP stdio transport, tool discovery
│   ├── input_validator.py        SI-3 / SI-10 input validation
│   └── path_enforcer.py          AC-3 / AC-6 path confinement
├── security/
│   └── audit_callback.py         LangChain BaseCallbackHandler → audit events
├── tools/
│   ├── github_tool.py            GitHub REST client (repo + file content)
│   ├── langchain_tools.py        @tool wrappers
│   └── mcp_langchain.py          MCP → LangChain StructuredTool adapter
├── frontend/
│   └── src/
│       ├── App.tsx               Router (dashboard + project detail)
│       ├── api.ts                Typed fetch wrappers
│       └── components/
│           ├── ChatPanel.tsx           Step-by-step approval chat
│           ├── ToolApprovalCard.tsx    Approve / Deny UI
│           ├── ToolStepCard.tsx        Collapsible tool result display
│           ├── ProjectDashboard.tsx    Project grid
│           ├── ProjectDetail.tsx       Project view + tabs
│           ├── TaskBoard.tsx           Kanban (todo / in-progress / done)
│           └── …                       MilestoneList, LogsView, etc.
└── tests/                        pytest suite (mirrors backend layout)
```

---

## Running it locally

```bash
# 1. Backend
pip install -r requirements.txt
export GOOGLE_API_KEY=...                # required for Gemini
python -m uvicorn api.server:app --reload --port 8000

# 2. Frontend (separate terminal)
cd frontend
npm install
npm run dev                              # → http://localhost:5173
```

Vite proxies `/api/*` to `localhost:8000`, so the frontend talks to the backend
without any CORS or URL shimming.

### Tests

```bash
pytest                          # Python: agent graph, tools, API, storage, audit
cd frontend && npx vitest run   # React: components, hooks, fetch wrappers
```

### Environment variables

| Variable | Purpose |
|---|---|
| `GOOGLE_API_KEY` | Required. Gemini API key for `langchain-google-genai`. |
| `AUDIT_LOG_DIR` | Override audit log directory (default: `.audit_logs/`). |

---

## Design notes

A few decisions worth calling out:

- **No CLI.** This is intentionally a web-only product. The audit, approval, and dashboard surfaces all assume a UI; a CLI would split the contract.
- **Pure-Python agent definitions.** An earlier iteration loaded agents from YAML. That was migrated out — the indirection didn't pay for itself once the project narrowed to one agent type, and Python lets the system prompt, model, and tool list live next to type-checked code.
- **LangGraph over raw SDK loops.** The interrupt-and-resume primitive is the whole reason the human-in-the-loop UX is feasible; rolling that by hand against a chat completion API would mean reimplementing checkpointing.
- **MCP as a first-class extensibility point.** New tools can be added without touching the agent code by configuring an MCP server (the GitHub MCP server is already wired up via `_MCP_CONFIGS` in `api/server.py`).
- **Audit log is a feature, not a debug tool.** `/api/logs` exposes sessions to a dedicated React view (`LogsView.tsx`), so the same FedRAMP-grade trail that supports compliance also doubles as the user's "what did the agent just do?" timeline.

---

## License

This project is provided as-is for portfolio and educational purposes.
