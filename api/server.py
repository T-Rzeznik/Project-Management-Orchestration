"""FastAPI server bridging the React frontend to the LangGraph agent."""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import asyncio
import ast
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api import storage
from api.models import (
    ChatRequest,
    ChatResponse,
    CreateProjectRequest,
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
                mgr = MCPClientManager()
                mgr.connect_all(_MCP_CONFIGS)
                _mcp_manager = mgr
            _mcp_initialized = True
    return _mcp_manager


def _get_agent():
    """Lazy-init singleton LangGraph agent."""
    global _agent
    if _agent is not None:
        return _agent
    with _agent_lock:
        if _agent is None:
            from agents.project_creator import build_agent
            from tools.langchain_tools import read_github_repo, create_project
            from tools.mcp_langchain import mcp_tools_as_langchain

            tools = [read_github_repo, create_project]
            mcp_mgr = _get_mcp_manager()
            tools.extend(mcp_tools_as_langchain(mcp_mgr))

            _agent = build_agent(tools=tools)
    return _agent


_TOOL_LABELS: dict[str, str] = {
    "read_github_repo": "Read GitHub Repository",
    "create_project": "Create Project",
}


def _tool_label(name: str) -> str:
    """Convert snake_case tool name to a human-friendly label."""
    if name in _TOOL_LABELS:
        return _TOOL_LABELS[name]
    return name.replace("_", " ").title()


def _summarize_tool_result(name: str, result: dict) -> str:
    """Return a one-line summary of a tool execution result."""
    if name == "read_github_repo":
        owner = result.get("owner", "")
        repo = result.get("repo", "")
        if owner and repo:
            file_count = len(result.get("file_tree", []))
            suffix = f" ({file_count} files)" if file_count else ""
            return f"Fetched {owner}/{repo}{suffix}"
    if name == "create_project":
        proj_name = result.get("name", "")
        if proj_name:
            return f"Created project: {proj_name}"
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

            # Try to parse the result as a dict for summary
            result_dict = {}
            try:
                parsed = ast.literal_eval(result_str) if result_str else {}
                if isinstance(parsed, dict):
                    result_dict = parsed
            except (ValueError, SyntaxError):
                try:
                    result_dict = json.loads(result_str)
                except (json.JSONDecodeError, TypeError):
                    pass

            steps.append({
                "tool_name": tool_name,
                "tool_label": _tool_label(tool_name),
                "args": tool_args,
                "summary": _summarize_tool_result(tool_name, result_dict),
                "detail": result_dict,
                "duration_ms": 0,
            })

    return steps


def _extract_token_counts(messages: list) -> tuple[int, int]:
    """Sum token counts from AIMessage.response_metadata across all messages."""
    from langchain_core.messages import AIMessage

    total_input = 0
    total_output = 0
    for msg in messages:
        if isinstance(msg, AIMessage):
            usage = (msg.response_metadata or {}).get("token_usage", {})
            total_input += usage.get("prompt_tokens", 0) or 0
            total_output += usage.get("completion_tokens", 0) or 0
    return total_input, total_output


def _find_created_project(messages: list) -> dict | None:
    """Check if create_project was called and find the resulting project."""
    from langchain_core.messages import AIMessage

    for msg in messages:
        if not isinstance(msg, AIMessage) or not msg.tool_calls:
            continue
        for tc in msg.tool_calls:
            if tc["name"] == "create_project":
                # The project was created by the tool — find it in storage
                projects = storage.list_projects()
                if projects:
                    return projects[-1]
    return None


def _call_agent(agent, messages: list[dict]) -> dict:
    """Invoke the LangGraph agent. Runs in thread pool."""
    from langchain_core.messages import HumanMessage, AIMessage as AI

    from agents.project_creator import AGENT_NAME, MODEL_NAME

    lc_messages = []
    for msg in messages:
        if msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        else:
            lc_messages.append(AI(content=msg["content"]))

    result = agent.invoke({"messages": lc_messages})

    result_messages = result["messages"]

    # Extract final text from last AI message
    from langchain_core.messages import AIMessage
    assistant_message = ""
    for msg in reversed(result_messages):
        if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
            assistant_message = msg.content
            break

    tool_steps = _extract_tool_steps(result_messages)
    total_input, total_output = _extract_token_counts(result_messages)
    created_project = _find_created_project(result_messages)

    return {
        "assistant_message": assistant_message,
        "input_tokens": total_input,
        "output_tokens": total_output,
        "project_created": created_project,
        "tool_steps": tool_steps,
        "agent_name": AGENT_NAME,
        "model_name": MODEL_NAME,
    }


@app.post("/api/chat")
async def chat(body: ChatRequest):
    agent = _get_agent()
    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            _executor, _call_agent, agent, messages
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return ChatResponse(**result)


@app.on_event("shutdown")
async def _shutdown_mcp():
    if _mcp_manager is not None:
        _mcp_manager.shutdown()
