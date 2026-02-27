"""Tests for the project API endpoints."""

import pytest
from fastapi.testclient import TestClient

from api.server import app
from api import storage


@pytest.fixture(autouse=True)
def clean_storage(tmp_path, monkeypatch):
    """Point storage at a temp file so tests don't touch real data."""
    monkeypatch.setattr(storage, "STORAGE_PATH", tmp_path / "projects.json")


client = TestClient(app)


def test_create_project_minimal():
    """POST /api/projects with only name should return a full project."""
    res = client.post("/api/projects", json={"name": "My Project"})
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "My Project"
    assert data["id"]  # auto-generated
    assert data["created_at"]
    assert data["github_url"] == ""
    assert data["documentation"] == ""
    assert data["tech_stack"] == []


def test_create_project_full():
    """POST /api/projects with all fields should persist them."""
    payload = {
        "name": "Full Project",
        "description": "A test project",
        "tech_stack": ["Python", "React"],
        "github_url": "https://github.com/test/repo",
        "documentation": "Some docs here",
    }
    res = client.post("/api/projects", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Full Project"
    assert data["description"] == "A test project"
    assert data["tech_stack"] == ["Python", "React"]
    assert data["github_url"] == "https://github.com/test/repo"
    assert data["documentation"] == "Some docs here"

    # Verify it was persisted
    res2 = client.get(f"/api/projects/{data['id']}")
    assert res2.status_code == 200
    assert res2.json()["name"] == "Full Project"


def test_create_project_missing_name():
    """POST /api/projects without name should return 422."""
    res = client.post("/api/projects", json={"description": "no name"})
    assert res.status_code == 422


# --- Update project tests ---


def _create_project(name: str = "Test Project", **kwargs) -> dict:
    """Helper: create a project and return its data."""
    res = client.post("/api/projects", json={"name": name, **kwargs})
    assert res.status_code == 200
    return res.json()


def test_update_project_name():
    """PUT /api/projects/{id} with just name should update it."""
    project = _create_project("Original Name")
    res = client.put(f"/api/projects/{project['id']}", json={"name": "New Name"})
    assert res.status_code == 200
    assert res.json()["name"] == "New Name"


def test_update_project_all_fields():
    """PUT /api/projects/{id} with all fields should update them all."""
    project = _create_project()
    payload = {
        "name": "Updated",
        "description": "Updated desc",
        "tech_stack": ["Go", "Rust"],
        "github_url": "https://github.com/new/repo",
        "documentation": "New docs",
        "status": "completed",
    }
    res = client.put(f"/api/projects/{project['id']}", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Updated"
    assert data["description"] == "Updated desc"
    assert data["tech_stack"] == ["Go", "Rust"]
    assert data["github_url"] == "https://github.com/new/repo"
    assert data["documentation"] == "New docs"
    assert data["status"] == "completed"


def test_update_project_not_found():
    """PUT /api/projects/{id} with nonexistent id should return 404."""
    res = client.put("/api/projects/nonexistent-id", json={"name": "X"})
    assert res.status_code == 404


def test_update_preserves_unset_fields():
    """PUT with only description should not wipe other fields."""
    project = _create_project(
        "Keep Me",
        description="Original",
        tech_stack=["Python"],
        documentation="Important notes",
    )
    res = client.put(
        f"/api/projects/{project['id']}",
        json={"description": "Changed"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Keep Me"
    assert data["description"] == "Changed"
    assert data["tech_stack"] == ["Python"]
    assert data["documentation"] == "Important notes"


# --- Task ID and task update tests ---


def test_task_has_auto_generated_id():
    """Tasks should receive a unique id when created via PUT."""
    project = _create_project("Task ID Project")
    res = client.put(
        f"/api/projects/{project['id']}",
        json={
            "tasks": [
                {"title": "Task A", "description": "Desc A"},
                {"title": "Task B", "description": "Desc B"},
            ]
        },
    )
    assert res.status_code == 200
    tasks = res.json()["tasks"]
    assert len(tasks) == 2
    assert tasks[0]["id"]  # UUID auto-generated
    assert tasks[1]["id"]
    assert tasks[0]["id"] != tasks[1]["id"]


def test_update_task_status_via_put():
    """PUT /api/projects/{id} with tasks should persist status changes."""
    project = _create_project("Kanban Project")
    # Add initial tasks
    res = client.put(
        f"/api/projects/{project['id']}",
        json={
            "tasks": [
                {"title": "Task A", "description": "Desc A", "status": "todo"},
                {"title": "Task B", "description": "Desc B", "status": "in-progress"},
            ]
        },
    )
    assert res.status_code == 200
    tasks = res.json()["tasks"]
    assert tasks[0]["status"] == "todo"

    # Move Task A to done
    tasks[0]["status"] = "done"
    res2 = client.put(
        f"/api/projects/{project['id']}",
        json={"tasks": tasks},
    )
    assert res2.status_code == 200
    assert res2.json()["tasks"][0]["status"] == "done"
    assert res2.json()["tasks"][1]["status"] == "in-progress"
