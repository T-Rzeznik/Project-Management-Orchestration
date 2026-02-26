"""Simple JSON file persistence for projects."""

from __future__ import annotations

import json
from pathlib import Path

STORAGE_PATH = Path(".projects.json")


def _load() -> list[dict]:
    if not STORAGE_PATH.exists():
        return []
    try:
        return json.loads(STORAGE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save(projects: list[dict]) -> None:
    STORAGE_PATH.write_text(
        json.dumps(projects, indent=2, default=str),
        encoding="utf-8",
    )


def list_projects() -> list[dict]:
    return _load()


def get_project(project_id: str) -> dict | None:
    for p in _load():
        if p.get("id") == project_id:
            return p
    return None


def save_project(project: dict) -> dict:
    projects = _load()
    for i, p in enumerate(projects):
        if p.get("id") == project.get("id"):
            projects[i] = project
            _save(projects)
            return project
    projects.append(project)
    _save(projects)
    return project


def delete_project(project_id: str) -> bool:
    projects = _load()
    new_projects = [p for p in projects if p.get("id") != project_id]
    if len(new_projects) == len(projects):
        return False
    _save(new_projects)
    return True
