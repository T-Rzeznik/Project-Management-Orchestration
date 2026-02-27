"""Tests for the project creation API endpoint."""

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
