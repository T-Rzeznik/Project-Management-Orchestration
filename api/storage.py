"""SQLite-backed project persistence."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(".projects.db")


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(str(DB_PATH))


def _init_db() -> None:
    """Create the projects table if it doesn't exist."""
    with _connect() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS projects "
            "(id TEXT PRIMARY KEY, data TEXT NOT NULL)"
        )


def list_projects() -> list[dict]:
    _init_db()
    with _connect() as conn:
        rows = conn.execute("SELECT data FROM projects").fetchall()
    return [json.loads(row[0]) for row in rows]


def get_project(project_id: str) -> dict | None:
    _init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT data FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
    if row is None:
        return None
    return json.loads(row[0])


def save_project(project: dict) -> dict:
    _init_db()
    data = json.dumps(project, default=str)
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO projects (id, data) VALUES (?, ?)",
            (project["id"], data),
        )
    return project


def delete_project(project_id: str) -> bool:
    _init_db()
    with _connect() as conn:
        cursor = conn.execute(
            "DELETE FROM projects WHERE id = ?", (project_id,)
        )
    return cursor.rowcount > 0
