"""Tests for POST /api/projects/from-github endpoint."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.server import app

client = TestClient(app)

FAKE_REPO_DATA = {
    "owner": "T-Rzeznik",
    "repo": "Sudoku",
    "name": "Sudoku",
    "description": "A Sudoku puzzle game",
    "stars": 5,
    "primary_language": "Python",
    "open_issues_count": 3,
    "languages": {"Python": 12000, "HTML": 3000},
    "contributors": ["T-Rzeznik", "contributor2"],
    "readme_content": "# Sudoku\nA puzzle game built in Python.",
    "recent_issues": [
        {"title": "Add difficulty selector", "number": 1},
        {"title": "Fix timer bug", "number": 2},
    ],
    "topics": ["sudoku", "python", "game"],
    "html_url": "https://github.com/T-Rzeznik/Sudoku",
    "file_tree": ["main.py", "board.py", "README.md"],
    "manifest_contents": {"requirements.txt": "pygame==2.5.0"},
}


@patch("api.server.fetch_repo_data", return_value=FAKE_REPO_DATA)
def test_import_from_github_creates_project(mock_fetch):
    resp = client.post(
        "/api/projects/from-github",
        json={"github_url": "https://github.com/T-Rzeznik/Sudoku"},
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["name"] == "Sudoku"
    assert data["description"] == "A Sudoku puzzle game"
    assert data["github_url"] == "https://github.com/T-Rzeznik/Sudoku"
    assert data["stars"] == 5
    assert data["language"] == "Python"
    assert data["open_issues_count"] == 3
    assert set(data["tech_stack"]) == {"Python", "HTML"}
    assert data["contributors"] == ["T-Rzeznik", "contributor2"]
    assert data["documentation"].startswith("# Sudoku")
    assert len(data["tasks"]) == 2
    assert data["tasks"][0]["title"] == "Add difficulty selector"
    assert data["tasks"][0]["status"] == "todo"
    assert data["tasks"][0]["priority"] == "medium"
    assert data["id"]  # has a UUID

    mock_fetch.assert_called_once_with("https://github.com/T-Rzeznik/Sudoku")


@patch("api.server.fetch_repo_data", side_effect=ValueError("Cannot parse GitHub identifier: not-a-url"))
def test_import_from_github_invalid_url_returns_400(mock_fetch):
    resp = client.post(
        "/api/projects/from-github",
        json={"github_url": "not-a-url"},
    )
    assert resp.status_code == 400
    assert "Cannot parse" in resp.json()["detail"]


def test_import_from_github_missing_url_returns_422():
    resp = client.post("/api/projects/from-github", json={})
    assert resp.status_code == 422
