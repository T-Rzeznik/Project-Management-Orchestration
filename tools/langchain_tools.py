"""LangChain @tool wrappers for the project management agent."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from langchain_core.tools import tool

from api import storage
from tools.github_tool import fetch_file_content, fetch_repo_data


@tool
def read_github_repo(github_url: str) -> dict:
    """Fetch public data from a GitHub repository including metadata, languages,
    contributors, README, open issues, file tree, and manifest files.

    Args:
        github_url: GitHub URL or owner/repo string (e.g. 'pallets/flask')
    """
    return fetch_repo_data(github_url)


@tool
def read_repo_file(owner: str, repo: str, path: str) -> str:
    """Read a single file from a public GitHub repository.

    Args:
        owner: Repository owner (e.g. 'pallets')
        repo: Repository name (e.g. 'flask')
        path: File path within the repo (e.g. 'src/flask/app.py')
    """
    return fetch_file_content(owner, repo, path)


@tool
def create_project(
    name: str,
    description: str = "",
    tech_stack: Optional[list[str]] = None,
    github_url: str = "",
    documentation: str = "",
    tasks: Optional[list[dict]] = None,
    milestones: Optional[list[dict]] = None,
) -> dict:
    """Create a new project entry in the dashboard with all relevant details.

    Args:
        name: Project name
        description: Project description
        tech_stack: List of technologies used
        github_url: GitHub repository URL
        documentation: Project documentation or summary
        tasks: List of tasks (each with title, description, priority, status)
        milestones: List of milestones (each with title, description)
    """
    now = datetime.utcnow().isoformat()
    task_list = tasks or []
    for t in task_list:
        t.setdefault("id", str(uuid.uuid4()))
        t.setdefault("priority", "medium")
        t.setdefault("status", "todo")

    project = {
        "id": str(uuid.uuid4()),
        "name": name,
        "description": description,
        "tech_stack": tech_stack or [],
        "github_url": github_url,
        "documentation": documentation,
        "tasks": task_list,
        "milestones": milestones or [],
        "status": "active",
        "stars": 0,
        "language": "",
        "open_issues_count": 0,
        "contributors": [],
        "summary": "",
        "created_at": now,
        "updated_at": now,
    }
    storage.save_project(project)
    return {"status": "created", "project_id": project["id"], "name": project["name"]}
