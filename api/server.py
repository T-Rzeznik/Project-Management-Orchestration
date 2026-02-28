"""FastAPI server bridging the React frontend to the orchestration framework."""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import asyncio
import json
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api import storage
from api.models import (
    AnalyzeRequest,
    ChatRequest,
    ChatResponse,
    CreateProjectRequest,
    Project,
    UpdateProjectRequest,
)

app = FastAPI(title="Project Management Orchestration API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_executor = ThreadPoolExecutor(max_workers=4)


def _parse_github_url(url: str) -> tuple[str, str]:
    """Extract owner and repo name from a GitHub URL."""
    m = re.search(r"github\.com/([^/]+)/([^/\s?#]+)", url)
    if not m:
        raise ValueError(f"Could not parse GitHub URL: {url}")
    owner = m.group(1)
    repo = m.group(2).rstrip("/").removesuffix(".git")
    return owner, repo


def _run_analyzer(github_url: str) -> dict:
    """Run the github_analyzer agent synchronously (called from thread pool)."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from framework.orchestrator import Orchestrator

    orch = Orchestrator(agents_dir="agents")
    yaml_path = Path(__file__).parent.parent / "agents" / "github_analyzer.yaml"

    result_str = orch.run_from_yaml(yaml_path, task=github_url)

    # Strip markdown code fences if the model wrapped the JSON
    result_str = result_str.strip()
    if result_str.startswith("```"):
        result_str = re.sub(r"^```(?:json)?\s*\n?", "", result_str)
        result_str = re.sub(r"\n?```\s*$", "", result_str)
    result_str = result_str.strip()

    return json.loads(result_str)


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

        # Derive session-level summary from events
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


@app.post("/api/analyze")
async def analyze_repo(body: AnalyzeRequest):
    github_url = body.github_url.strip()

    try:
        _parse_github_url(github_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    loop = asyncio.get_event_loop()
    try:
        project_data = await loop.run_in_executor(_executor, _run_analyzer, github_url)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Agent returned non-JSON output: {exc}",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    now = datetime.utcnow().isoformat()
    project = {
        "id": str(uuid.uuid4()),
        "github_url": github_url,
        "created_at": now,
        "updated_at": now,
        **project_data,
    }

    storage.save_project(project)
    return project


@app.post("/api/projects")
async def create_project(body: CreateProjectRequest):
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


@app.get("/api/projects")
async def list_projects():
    return storage.list_projects()


@app.put("/api/projects/{project_id}")
async def update_project(project_id: str, body: UpdateProjectRequest):
    """Update an existing project (partial update — only provided fields are changed)."""
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


# --- AI Chat ---

_chat_provider = None

_CHAT_SYSTEM_PROMPT = (
    "You are a helpful AI assistant integrated into a project management application."
)


def _get_chat_provider():
    """Lazy-init singleton Gemini GenerativeModel for chat."""
    global _chat_provider
    if _chat_provider is None:
        import os
        import google.generativeai as genai

        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        _chat_provider = genai
    return _chat_provider


def _call_chat_provider(genai_mod, model: str, messages: list[dict]) -> dict:
    """Blocking call to Gemini — runs in thread pool."""
    gmodel = genai_mod.GenerativeModel(
        model_name=model,
        system_instruction=_CHAT_SYSTEM_PROMPT,
    )

    # Convert messages to Gemini content format
    contents = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [msg["content"]]})

    response = gmodel.generate_content(contents)

    usage = response.usage_metadata
    return {
        "assistant_message": response.text,
        "input_tokens": getattr(usage, "prompt_token_count", 0) or 0,
        "output_tokens": getattr(usage, "candidates_token_count", 0) or 0,
    }


@app.post("/api/chat")
async def chat(body: ChatRequest):
    provider = _get_chat_provider()
    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            _executor, _call_chat_provider, provider, body.model, messages
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return ChatResponse(**result)
