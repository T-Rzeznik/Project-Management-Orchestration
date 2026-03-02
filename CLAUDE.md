# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the stack

```bash
# Python backend — install deps
pip install -r requirements.txt

# Start the FastAPI bridge (from project root)
python -m uvicorn api.server:app --reload --port 8000

# Start the React frontend (separate terminal)
cd frontend && npm install && npm run dev   # → http://localhost:5173
```

## Development Methodology: Test-Driven Development (TDD)

This project enforces Test-Driven Development. Every code change follows the Red-Green-Refactor cycle:

1. **Red** — Write a failing test that defines the expected behavior. Run it and confirm it fails.
2. **Green** — Write the minimum implementation code to make the test pass. Run the test and confirm it passes.
3. **Refactor** — Clean up the implementation while keeping tests green. Run the full suite to confirm no regressions.

### Hard Rules

- **No implementation code without a failing test first.** If you are about to write a function, endpoint, component, or module, you must first write a test that exercises it and confirm the test fails (Red phase).
- **No skipping the Red phase.** Running the test and seeing it fail is mandatory. This proves the test actually tests something.
- **Tests are not optional or deferred.** "I'll add tests later" is not acceptable. Tests come first, always.
- **Refactoring requires a green suite.** Before and after every refactor step, the full test suite must pass.

### Test Tooling

**Python (framework + API):**
- Test runner: `pytest`
- Async tests: `pytest-asyncio`
- HTTP/API tests: `httpx` (with `TestClient` for FastAPI)
- Test directory: `tests/` at project root, mirroring `framework/` and `api/` structure
- Naming: `test_<module>.py` with functions named `test_<behavior>()`
- Run: `pytest` (from project root)

**Frontend (React + TypeScript):**
- Test runner: `vitest`
- Component testing: `@testing-library/react` + `@testing-library/jest-dom`
- DOM environment: `jsdom`
- Test files: colocated as `<Component>.test.tsx` or in `__tests__/` directories
- Naming: `describe('<Component>')` with `it('should <behavior>')` blocks
- Run: `cd frontend && npx vitest run`

### TDD Workflow Example (Python)

```bash
# 1. Write the test in tests/test_langchain_tools.py
# 2. Run it — expect failure:
pytest tests/test_langchain_tools.py -v
# 3. Implement just enough in tools/langchain_tools.py
# 4. Run again — expect pass:
pytest tests/test_langchain_tools.py -v
# 5. Refactor, run full suite:
pytest
```

### TDD Workflow Example (Frontend)

```bash
# 1. Write the test in frontend/src/components/ProjectCard.test.tsx
# 2. Run it — expect failure:
cd frontend && npx vitest run src/components/ProjectCard.test.tsx
# 3. Implement just enough in ProjectCard.tsx
# 4. Run again — expect pass
# 5. Refactor, run full suite:
cd frontend && npx vitest run
```

## Architecture

### LangChain + LangGraph Agent Layer (Python)

The AI agent is built with LangChain and LangGraph, using Gemini as the LLM provider:

```
agents/
  project_creator.py      Pure Python agent definition using create_react_agent
security/
  audit_callback.py       LangChain BaseCallbackHandler → FedRAMP audit events
tools/
  github_tool.py          fetch_repo_data() — GitHub REST API client
  langchain_tools.py      @tool wrappers: read_github_repo, create_project
  mcp_langchain.py        MCP-to-LangChain adapter (StructuredTool wrappers)
framework/
  audit_logger.py         Append-only JSONL audit log (AU-2/3/8/9/12)
  secret_scrubber.py      Regex-based redaction before audit writes (SC-28)
  mcp_client.py           MCP stdio transport — tool discovery and call dispatch
  path_enforcer.py        Resolves symlinks, blocks traversal (AC-3/AC-6/AU-9)
  input_validator.py      SI-3 bash blocklist, SI-10 URL/SSRF/size checks
```

**Agent flow:** `api/server.py` builds a LangGraph `create_react_agent` with LangChain tools + MCP tools. The agent handles the full ReAct loop (LLM → tool calls → tool results → LLM → ... → text response). The server extracts tool steps and token counts from the LangGraph message list.

**Provider:** All agents use `langchain-google-genai` (`ChatGoogleGenerativeAI`) with Gemini models. MCP tools are auto-converted to LangChain `StructuredTool` via `tools/mcp_langchain.py`.

### FastAPI + React frontend

```
api/
  server.py     Endpoints: POST /api/chat, POST/GET/PUT/DELETE /api/projects,
                POST /api/projects/from-github, GET /api/logs
                Uses LangGraph agent in a ThreadPoolExecutor
  storage.py    Reads/writes .projects.json (flat JSON list, no database)
  models.py     Pydantic: Project, Task, ChatRequest, ChatResponse, ToolStep
frontend/src/
  App.tsx                 React Router: / and /projects/:id
  api.ts                  fetch wrappers for all API endpoints
  components/
    ProjectDashboard.tsx  Grid of ProjectCards + create project trigger
    ProjectCard.tsx       Summary card; navigates to detail on click
    ChatPanel.tsx         AI chat panel with tool step display
    CreateProjectModal.tsx  Manual project creation form
    ToolStepCard.tsx      Collapsible tool execution display
    ProjectDetail.tsx     Full project view with TaskBoard, MilestoneList
    TaskBoard.tsx         3-column kanban (todo / in-progress / done)
```

Vite proxies all `/api/*` requests to `http://localhost:8000` in dev mode (`vite.config.ts`).

## Adding a new agent

1. Create `agents/myagent.py` with `AGENT_NAME`, `MODEL_NAME`, `SYSTEM_PROMPT`, and a `build_agent(tools, callbacks)` function.
2. The `build_agent` function should use `create_react_agent` from `langgraph.prebuilt` with `ChatGoogleGenerativeAI`.
3. Add LangChain `@tool` wrappers in `tools/langchain_tools.py` for any new tools.
4. Write tests in `tests/` following TDD (red-green-refactor).

## Environment variables

| Variable | Purpose |
|---|---|
| `GOOGLE_API_KEY` | Required for Gemini via langchain-google-genai |
| `AUDIT_LOG_DIR` | Override audit log directory (default: `.audit_logs/`) |

## Skills

- `/commit-push` — Analyzes the diff, runs tests (pytest + vitest), generates a commit message, and pushes to main. Triggers on "commit and push", "push my changes", "ship it". Blocks on secrets or test failures. Confirms before pushing.
- `/dev` — Starts all dev services (FastAPI backend on :8000 + React frontend on :5173). Checks deps and port availability, runs both in background, opens browser. Triggers on "start the app", "run dev", "spin up services".
- `/test-playwright` — Runs the full test pipeline: pytest + vitest + Playwright e2e. Checks if dev services are running (starts them if needed), runs all three suites with timeout protection, and prints a combined pass/fail summary. Auto-invoked on "run all tests", "test everything", "run the test suite".
- `/current-development` — Scans both stacks (Python + React) to produce a feature inventory: what's complete, in progress, or stubbed. Finds TODOs/FIXMEs and suggests prioritized next steps. Read-only, fast. Auto-invoked on "project status", "where are we in the build?", "what's been built?".

## FedRAMP controls at a glance

Every tool call produces audit events via `security/audit_callback.py` (`TOOL_CALL_PROPOSED` on start, `TOOL_EXECUTED` on success, `TOOL_BLOCKED` on error). Secret scrubbing runs on tool args before any audit write. The audit log directory is protected from agent modification.
