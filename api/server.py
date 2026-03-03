"""FastAPI server bridging the React frontend to the LangGraph agent."""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import asyncio
import ast
import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api import storage
from api.models import (
    ApproveRequest,
    ChatRequest,
    ChatResponse,
    ChatStepResponse,
    CreateProjectRequest,
    DenyRequest,
    ImportGithubRequest,
    Project,
    Task,
    UpdateProjectRequest,
)
from framework.mcp_client import MCPClientManager
from tools.github_tool import fetch_repo_data

app = FastAPI(title="Project Management Orchestration API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_executor = ThreadPoolExecutor(max_workers=4)

# --- Thread registry for step-by-step agent execution ---
_threads: dict[str, float] = {}  # thread_id -> creation timestamp
_threads_lock = threading.Lock()


def _create_thread() -> str:
    """Create a new thread ID and register it."""
    _cleanup_threads()
    tid = str(uuid.uuid4())
    with _threads_lock:
        _threads[tid] = time.time()
    return tid


def _thread_exists(thread_id: str) -> bool:
    """Check if a thread ID is registered."""
    with _threads_lock:
        return thread_id in _threads


def _cleanup_threads(max_age_seconds: int = 3600) -> None:
    """Remove threads older than max_age_seconds."""
    cutoff = time.time() - max_age_seconds
    with _threads_lock:
        expired = [tid for tid, ts in _threads.items() if ts < cutoff]
        for tid in expired:
            del _threads[tid]


@app.get("/api/logs")
async def list_log_sessions():
    """Return all audit log sessions from .audit_logs/*.jsonl, newest first."""
    log_dir = Path(__file__).parent.parent / ".audit_logs"
    if not log_dir.exists():
        return []

    sessions = []
    for log_file in sorted(log_dir.glob("*.jsonl"), reverse=True)[:100]:
        events = []
        try:
            with open(log_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))
        except (OSError, json.JSONDecodeError):
            continue

        if not events:
            continue

        start_evt = next((e for e in events if e.get("event_type") == "SESSION_START"), events[0])
        end_evt = next((e for e in events if e.get("event_type") == "AGENT_TASK_END"), None)
        agent_names = list(dict.fromkeys(
            e["agent_name"] for e in events if e.get("agent_name")
        ))
        total_input = sum(e.get("total_input_tokens", 0) or 0 for e in events)
        total_output = sum(e.get("total_output_tokens", 0) or 0 for e in events)

        sessions.append({
            "session_id": start_evt.get("session_id", log_file.stem),
            "file": log_file.name,
            "start_time": start_evt.get("timestamp_utc"),
            "operator": start_evt.get("operator"),
            "agent_names": agent_names,
            "event_count": len(events),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "events": events,
        })

    return sessions


@app.post("/api/projects")
async def create_project_endpoint(body: CreateProjectRequest):
    """Create a project manually (no GitHub analysis)."""
    project = Project(
        name=body.name,
        description=body.description,
        tech_stack=body.tech_stack,
        github_url=body.github_url,
        documentation=body.documentation,
    )
    storage.save_project(project.model_dump())
    return project.model_dump()


def _import_from_github(github_url: str) -> dict:
    """Fetch repo data and map to a Project dict. Runs in thread pool."""
    repo_data = fetch_repo_data(github_url)

    tasks = [
        Task(
            title=issue["title"],
            description=f"GitHub issue #{issue['number']}",
            status="todo",
            priority="medium",
        ).model_dump()
        for issue in repo_data.get("recent_issues", [])
    ]

    project = Project(
        name=repo_data["name"],
        description=repo_data.get("description", ""),
        tech_stack=list(repo_data.get("languages", {}).keys()),
        github_url=repo_data.get("html_url", ""),
        stars=repo_data.get("stars", 0),
        language=repo_data.get("primary_language", ""),
        open_issues_count=repo_data.get("open_issues_count", 0),
        contributors=repo_data.get("contributors", []),
        documentation=repo_data.get("readme_content", "")[:5000],
        tasks=tasks,
    )
    result = project.model_dump()
    storage.save_project(result)
    return result


@app.post("/api/projects/from-github")
async def import_from_github(body: ImportGithubRequest):
    """Import a project directly from a GitHub URL — no AI agent needed."""
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            _executor, _import_from_github, body.github_url
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result


@app.get("/api/projects")
async def list_projects():
    return storage.list_projects()


@app.put("/api/projects/{project_id}")
async def update_project(project_id: str, body: UpdateProjectRequest):
    """Update an existing project (partial update)."""
    existing = storage.get_project(project_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Project not found")

    updates = body.model_dump(exclude_none=True)
    existing.update(updates)
    existing["updated_at"] = datetime.utcnow().isoformat()

    storage.save_project(existing)
    return existing


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    project = storage.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    if not storage.delete_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"message": "Project deleted"}


# --- AI Chat (LangGraph Agent) ---

_agent = None
_agent_lock = threading.Lock()

_mcp_manager: MCPClientManager | None = None
_mcp_lock = threading.Lock()
_mcp_initialized = False

# MCP server configs from agent definition
_MCP_CONFIGS: list[dict] = [
    {
        "name": "github",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
    },
]


def _get_mcp_manager() -> MCPClientManager | None:
    """Lazy-init singleton MCP client manager."""
    global _mcp_manager, _mcp_initialized
    if _mcp_initialized:
        return _mcp_manager
    with _mcp_lock:
        if not _mcp_initialized:
            if _MCP_CONFIGS:
                try:
                    mgr = MCPClientManager()
                    mgr.connect_all(_MCP_CONFIGS)
                    _mcp_manager = mgr
                except RuntimeError as exc:
                    import logging
                    logging.warning(f"MCP init failed ({exc}); agent will run without MCP tools")
            _mcp_initialized = True
    return _mcp_manager


def _get_agent():
    """Lazy-init singleton LangGraph agent with MemorySaver and interrupt_before."""
    global _agent
    if _agent is not None:
        return _agent
    with _agent_lock:
        if _agent is None:
            from langgraph.checkpoint.memory import MemorySaver

            from agents.project_creator import build_agent
            from tools.langchain_tools import read_github_repo, read_repo_file, create_project
            from tools.mcp_langchain import mcp_tools_as_langchain

            tools = [read_github_repo, read_repo_file, create_project]
            mcp_mgr = _get_mcp_manager()
            tools.extend(mcp_tools_as_langchain(mcp_mgr))

            checkpointer = MemorySaver()
            _agent = build_agent(
                tools=tools,
                checkpointer=checkpointer,
                interrupt_before=["tools"],
            )
    return _agent


_TOOL_LABELS: dict[str, str] = {
    "read_github_repo": "Read GitHub Repository",
    "read_repo_file": "Read Repository File",
    "create_project": "Create Project",
}


def _tool_label(name: str) -> str:
    """Convert snake_case tool name to a human-friendly label."""
    if name in _TOOL_LABELS:
        return _TOOL_LABELS[name]
    return name.replace("_", " ").title()


def _extract_pending_tools(messages: list) -> list[dict]:
    """Find pending tool calls from the last AIMessage with tool_calls.

    Used when the graph interrupts before the tools node.
    """
    from langchain_core.messages import AIMessage

    # Walk backwards to find the last AIMessage with tool_calls
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.tool_calls:
            return [
                {
                    "tool_name": tc["name"],
                    "tool_label": _tool_label(tc["name"]),
                    "args": tc["args"],
                    "tool_call_id": tc["id"],
                }
                for tc in msg.tool_calls
            ]
    return []


def _summarize_tool_result(name: str, result) -> str:
    """Return a one-line summary of a tool execution result."""
    if name == "read_github_repo" and isinstance(result, dict):
        owner = result.get("owner", "")
        repo = result.get("repo", "")
        if owner and repo:
            file_count = len(result.get("file_tree", []))
            suffix = f" ({file_count} files)" if file_count else ""
            return f"Fetched {owner}/{repo}{suffix}"
    if name == "create_project" and isinstance(result, dict):
        proj_name = result.get("name", "")
        if proj_name:
            return f"Created project: {proj_name}"
    if name == "read_repo_file":
        if isinstance(result, str) and result:
            return f"Read file ({len(result)} chars)"
        return "File not found or empty"
    return "Completed"


def _extract_tool_steps(messages: list) -> list[dict]:
    """Walk LangGraph message list and build ToolStep dicts from AIMessage.tool_calls + ToolMessage pairs."""
    from langchain_core.messages import AIMessage, ToolMessage

    tool_results: dict[str, str] = {}
    for msg in messages:
        if isinstance(msg, ToolMessage):
            tool_results[msg.tool_call_id] = msg.content

    steps = []
    for msg in messages:
        if not isinstance(msg, AIMessage) or not msg.tool_calls:
            continue
        for tc in msg.tool_calls:
            tool_name = tc["name"]
            tool_args = tc["args"]
            result_str = tool_results.get(tc["id"], "")

            # Try to parse the result as a dict; keep raw string as fallback
            result_parsed = {}
            try:
                parsed = ast.literal_eval(result_str) if result_str else {}
                if isinstance(parsed, dict):
                    result_parsed = parsed
                else:
                    result_parsed = result_str
            except (ValueError, SyntaxError):
                try:
                    result_parsed = json.loads(result_str)
                except (json.JSONDecodeError, TypeError):
                    # Keep the raw string so tools returning text aren't lost
                    if result_str:
                        result_parsed = result_str

            steps.append({
                "tool_name": tool_name,
                "tool_label": _tool_label(tool_name),
                "args": tool_args,
                "summary": _summarize_tool_result(tool_name, result_parsed),
                "detail": result_parsed,
                "duration_ms": 0,
            })

    return steps


def _extract_token_counts(messages: list) -> tuple[int, int]:
    """Sum token counts from AIMessage across all messages.

    Gemini (via langchain-google-genai) stores counts in
    ``AIMessage.usage_metadata`` with keys ``input_tokens`` /
    ``output_tokens``.  OpenAI-style providers use
    ``response_metadata.token_usage`` with ``prompt_tokens`` /
    ``completion_tokens``.  We check both.
    """
    from langchain_core.messages import AIMessage

    total_input = 0
    total_output = 0
    for msg in messages:
        if not isinstance(msg, AIMessage):
            continue

        # Gemini path: usage_metadata.input_tokens / output_tokens
        um = getattr(msg, "usage_metadata", None) or {}
        if isinstance(um, dict) and (um.get("input_tokens") or um.get("output_tokens")):
            total_input += um.get("input_tokens", 0) or 0
            total_output += um.get("output_tokens", 0) or 0
            continue

        # Legacy / OpenAI path: response_metadata.token_usage
        usage = (msg.response_metadata or {}).get("token_usage", {})
        total_input += usage.get("prompt_tokens", 0) or 0
        total_output += usage.get("completion_tokens", 0) or 0
    return total_input, total_output


def _find_created_project(messages: list) -> dict | None:
    """Check if create_project was called and find the resulting project.

    Fallback: if the agent called read_github_repo but skipped create_project,
    auto-create the project from the repo data so it actually appears in the
    dashboard.
    """
    from langchain_core.messages import AIMessage, ToolMessage

    called_create = False
    repo_data: dict | None = None

    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc["name"] == "create_project":
                    called_create = True
                if tc["name"] == "read_github_repo":
                    # Grab the corresponding ToolMessage result
                    for tmsg in messages:
                        if isinstance(tmsg, ToolMessage) and tmsg.tool_call_id == tc["id"]:
                            try:
                                repo_data = ast.literal_eval(tmsg.content) if isinstance(tmsg.content, str) else tmsg.content
                            except (ValueError, SyntaxError):
                                try:
                                    repo_data = json.loads(tmsg.content)
                                except (json.JSONDecodeError, TypeError):
                                    pass

    if called_create:
        projects = storage.list_projects()
        if projects:
            return projects[-1]
        return None

    # Fallback: agent read the repo but never called create_project
    if repo_data and isinstance(repo_data, dict):
        from tools.langchain_tools import create_project
        create_project.invoke({
            "name": repo_data.get("name", "Untitled"),
            "description": repo_data.get("description", ""),
            "tech_stack": list(repo_data.get("languages", {}).keys()),
            "github_url": repo_data.get("html_url", ""),
            "documentation": (repo_data.get("readme_content", "") or "")[:5000],
        })
        projects = storage.list_projects()
        if projects:
            return projects[-1]

    return None


import re

_CTRL_TOKEN_RE = re.compile(r"<ctrl\d+>")


def _sanitize_content(content) -> str:
    """Normalize AIMessage.content to a clean string.

    Gemini sometimes returns content as a list of parts, some of which are
    control tokens like ``<ctrl42>`` (internal function-calling signals) or
    raw code snippets like ``call\\nprint(default_api.…)``.  This helper
    extracts only genuine natural-language text.
    """
    if isinstance(content, str):
        parts = [content]
    elif isinstance(content, list):
        parts = [p for p in content if isinstance(p, str)]
    else:
        return str(content)

    cleaned = []
    for part in parts:
        # Drop Gemini control tokens
        if _CTRL_TOKEN_RE.fullmatch(part.strip()):
            continue
        # Drop parts that look like raw generated code calls
        if part.strip().startswith("call\n") or "default_api." in part:
            continue
        cleaned.append(part)

    return " ".join(cleaned).strip()


def _extract_assistant_message(result_messages: list) -> str:
    """Extract the final assistant text from the LangGraph message list."""
    from langchain_core.messages import AIMessage

    # First pass: prefer a pure-text AIMessage (no tool_calls).
    for msg in reversed(result_messages):
        if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
            text = _sanitize_content(msg.content)
            if text:
                return text
    # Second pass: fall back to any AIMessage with content.
    for msg in reversed(result_messages):
        if isinstance(msg, AIMessage) and msg.content:
            text = _sanitize_content(msg.content)
            if text:
                return text
    return ""


def _build_step_response(agent, config: dict, result_messages: list) -> dict:
    """Build a ChatStepResponse dict from agent state after invoke.

    Checks agent.get_state(config).next to determine if the graph is
    interrupted (tool_pending) or complete (done).
    """
    from agents.project_creator import AGENT_NAME, MODEL_NAME

    state = agent.get_state(config)
    is_interrupted = "tools" in (state.next or ())

    if is_interrupted:
        pending = _extract_pending_tools(result_messages)
        completed = _extract_tool_steps(result_messages)
        total_input, total_output = _extract_token_counts(result_messages)
        return {
            "status": "tool_pending",
            "thread_id": config["configurable"]["thread_id"],
            "pending_tools": pending,
            "completed_steps": completed,
            "assistant_message": "",
            "input_tokens": total_input,
            "output_tokens": total_output,
            "agent_name": AGENT_NAME,
            "model_name": MODEL_NAME,
        }

    # Done — graph completed
    assistant_message = _extract_assistant_message(result_messages)
    tool_steps = _extract_tool_steps(result_messages)
    total_input, total_output = _extract_token_counts(result_messages)
    created_project = _find_created_project(result_messages)

    # Fallback: if the LLM didn't produce visible text (Gemini sometimes
    # generates only reasoning tokens), build a summary from tool steps.
    if not assistant_message and (tool_steps or created_project):
        parts = []
        for step in tool_steps:
            parts.append(f"- **{step['tool_label']}**: {step['summary']}")
        if created_project:
            name = created_project.get("name", "")
            desc = created_project.get("description", "")
            parts.append(f"\nProject **{name}** has been created and added to your dashboard.")
            if desc:
                parts.append(f"\n> {desc}")
        assistant_message = "\n".join(parts) if parts else "Analysis complete."

    return {
        "status": "done",
        "thread_id": config["configurable"]["thread_id"],
        "pending_tools": [],
        "completed_steps": tool_steps,
        "assistant_message": assistant_message,
        "input_tokens": total_input,
        "output_tokens": total_output,
        "project_created": created_project,
        "tool_steps": tool_steps,
        "agent_name": AGENT_NAME,
        "model_name": MODEL_NAME,
    }


def _call_agent(agent, messages: list[dict], thread_id: str) -> dict:
    """Invoke the LangGraph agent with a thread. Runs in thread pool."""
    from langchain_core.messages import HumanMessage, AIMessage as AI

    config = {"configurable": {"thread_id": thread_id}}

    lc_messages = []
    for msg in messages:
        if msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        else:
            lc_messages.append(AI(content=msg["content"]))

    result = agent.invoke({"messages": lc_messages}, config=config)
    # Use full state messages — invoke() may return only delta for checkpointed graphs
    full_messages = agent.get_state(config).values.get("messages", [])
    return _build_step_response(agent, config, full_messages)


def _resume_agent(agent, thread_id: str) -> dict:
    """Resume a paused agent (after approve). Runs in thread pool."""
    config = {"configurable": {"thread_id": thread_id}}
    result = agent.invoke(None, config=config)
    # invoke(None) may return only delta messages; use full state for extraction
    full_messages = agent.get_state(config).values.get("messages", [])
    return _build_step_response(agent, config, full_messages)


def _deny_and_resume(agent, thread_id: str, reason: str) -> dict:
    """Inject denial ToolMessages and resume the agent. Runs in thread pool."""
    from langchain_core.messages import ToolMessage

    config = {"configurable": {"thread_id": thread_id}}
    state = agent.get_state(config)
    result_messages = state.values.get("messages", [])
    pending = _extract_pending_tools(result_messages)

    # Inject a ToolMessage with the denial for each pending tool call
    denial_messages = [
        ToolMessage(content=reason, tool_call_id=pt["tool_call_id"], name=pt["tool_name"])
        for pt in pending
    ]
    agent.update_state(config, {"messages": denial_messages}, as_node="tools")

    # Resume — the LLM sees the denial and adapts
    result = agent.invoke(None, config=config)
    full_messages = agent.get_state(config).values.get("messages", [])
    return _build_step_response(agent, config, full_messages)


@app.post("/api/chat")
async def chat(body: ChatRequest):
    agent = _get_agent()
    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    thread_id = _create_thread()
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            _executor, _call_agent, agent, messages, thread_id
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return ChatStepResponse(**result)


@app.post("/api/chat/approve")
async def approve_tool(body: ApproveRequest):
    if not _thread_exists(body.thread_id):
        raise HTTPException(status_code=404, detail="Thread not found")

    agent = _get_agent()
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            _executor, _resume_agent, agent, body.thread_id
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return ChatStepResponse(**result)


@app.post("/api/chat/deny")
async def deny_tool(body: DenyRequest):
    if not _thread_exists(body.thread_id):
        raise HTTPException(status_code=404, detail="Thread not found")

    agent = _get_agent()
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            _executor, _deny_and_resume, agent, body.thread_id, body.reason
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return ChatStepResponse(**result)


@app.on_event("shutdown")
async def _shutdown_mcp():
    if _mcp_manager is not None:
        _mcp_manager.shutdown()
