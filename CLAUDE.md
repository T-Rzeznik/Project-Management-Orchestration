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

## CLI usage (framework only, no UI)

```bash
# Run a single agent on a task
python main.py run agents/researcher.yaml "Research quantum computing"

# Multi-agent workflow via an orchestrator agent
python main.py orchestrate agents/orchestrator.yaml "Build a Python web scraper"

# Interactive chat
python main.py chat agents/coder.yaml --operator "alice"

# Inspect an agent's tools without running it
python main.py list-tools agents/github_analyzer.yaml
```

## Architecture

This repo has two mostly-independent layers:

### 1. YAML-based agent orchestration framework (Python)

```
main.py                 Typer CLI — creates SessionContext + AuditLogger, runs Orchestrator
framework/
  orchestrator.py       Loads agent YAMLs, wires all security components, exposes run_task() / run_from_yaml()
  agent.py              Agentic loop: calls provider, dispatches tool_use blocks, extracts final text
  providers/
    factory.py          create_provider(config) — reads provider.type from agent YAML
    anthropic_provider.py  Wraps anthropic.Anthropic()
    vertex_provider.py  Claude via AnthropicVertex, Gemini via vertexai SDK (stateful ChatSession)
    base.py             BaseProvider, NormalizedResponse, NormalizedTextBlock, NormalizedToolUseBlock
  verification.py       Human-in-the-loop gate: y/n/e before every tool call; emits audit events
  tool_registry.py      Per-agent allowed tool list; calls factory functions bound to PathEnforcer
  path_enforcer.py      Resolves symlinks, blocks ../ traversal, protects audit log dir (AC-3/AC-6/AU-9)
  audit_logger.py       Append-only JSONL audit log; synchronous flush per record (AU-2/3/8/9/12)
  schema.py             jsonschema validation of agent YAML; FedRAMP policy check (no 'never' + high-risk tools)
  input_validator.py    SI-3 bash blocklist, SI-10 URL/SSRF/size checks, post-edit arg re-validation
  secret_scrubber.py    Regex-based redaction before writing args/results to audit log (SC-28)
  mcp_client.py         MCP stdio transport — tool discovery and call dispatch
tools/
  bash_tool.py          bash — SI-3 filtered, cwd confined to first allowed_root, timeout capped 300s
  file_tools.py         read_file, write_file, list_dir — all AC-3 enforced via PathEnforcer
  web_tools.py          web_fetch — SSRF blocked, http/https only, redirect not followed, 10 MB cap
agents/                 YAML definitions for each agent (see schema section below)
```

**Critical data flow:** `Orchestrator.build_agent()` creates a fresh `PathEnforcer`, `VerificationGate`, `ToolRegistry`, and `Provider` per agent — these are not shared across agents. Each agent's tool callables are closures bound to that agent's `PathEnforcer` at construction time.

**Provider routing (Vertex AI):** model name starting with `claude-` → `AnthropicVertex`; anything else (e.g. `gemini-2.0-flash-lite`) → `vertexai.GenerativeModel` with a stateful `ChatSession`. The Gemini path strips `additionalProperties`, `$schema`, `$defs` from tool schemas before sending to Gemini (it doesn't support them).

### 2. FastAPI + React frontend

```
api/
  server.py     4 endpoints: POST /api/analyze, GET/DELETE /api/projects, GET /api/projects/{id}
                Runs the github_analyzer agent in a ThreadPoolExecutor (keeps FastAPI non-blocking)
  storage.py    Reads/writes .projects.json (flat JSON list, no database)
  models.py     Pydantic: Project, Task, Milestone, AnalyzeRequest
frontend/src/
  App.tsx                 React Router: / and /projects/:id
  api.ts                  fetch wrappers for all 4 API endpoints
  components/
    ProjectDashboard.tsx  Grid of ProjectCards + AnalyzeModal trigger
    ProjectCard.tsx       Summary card; navigates to detail on click
    AnalyzeModal.tsx      GitHub URL input with spinner
    ProjectDetail.tsx     Full project view with TaskBoard, MilestoneList, ContributorAvatars
    TaskBoard.tsx         3-column kanban (todo / in-progress / done)
```

Vite proxies all `/api/*` requests to `http://localhost:8000` in dev mode (`vite.config.ts`).

## Agent YAML schema

Required fields: `name`, `model`, `system_prompt`.

Key optional fields:
```yaml
provider:
  type: vertex_ai          # or "anthropic" (default)
  project: my-gcp-project
  location: us-central1

tools:
  builtin: [read_file, write_file, list_dir, bash, web_fetch]
  mcp:
    - name: myserver
      transport: stdio     # only stdio is implemented; sse logs a warning and skips
      command: npx
      args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]

allowed_paths: [.]         # omitting defaults to CWD with a warning

verification:
  mode: always             # always | selective | never
  require_for: [bash, write_file]   # used with selective

handoff:
  can_delegate_to: [researcher, coder]   # injects delegate_to_agent tool

max_turns: 20
```

**Hard constraint:** `verification.mode: never` + `bash` or `write_file` is a load-time `ValueError` (FedRAMP CM-6). `web_fetch` with `never` mode is fine.

## Adding a new agent

1. Create `agents/myagent.yaml` following the schema above.
2. Add the agent's `provider` block if using Vertex AI.
3. All agents are auto-loaded by `Orchestrator.load_agents_dir()` (used by `orchestrate` CLI command and the FastAPI server on analysis requests).

## Environment variables

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Required for Anthropic-backed agents |
| `AUDIT_LOG_DIR` | Override audit log directory (default: `.audit_logs/`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | GCP service account key for Vertex AI (alternative to `gcloud auth application-default login`) |

## FedRAMP controls at a glance

Every tool call produces two audit events (`TOOL_CALL_PROPOSED` before showing to the human, `VERIFICATION_DECISION` after). The audit log directory is always added to `PathEnforcer.protected_dirs` so agents cannot modify their own logs. Secret scrubbing runs on tool args before any audit write; the console shows real args to the authorized operator.
