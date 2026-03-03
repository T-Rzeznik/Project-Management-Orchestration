"""Tests for the project API endpoints."""

import pytest
from fastapi.testclient import TestClient

from api.server import app
from api import storage


@pytest.fixture(autouse=True)
def clean_storage(tmp_path, monkeypatch):
    """Point storage at a temp SQLite DB so tests don't touch real data."""
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "test.db")
    storage._init_db()


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


# --- Step-by-step agent models ---


class TestPendingToolModel:
    def test_pending_tool_fields(self):
        """PendingTool should have tool_name, tool_label, args, tool_call_id."""
        from api.models import PendingTool

        pt = PendingTool(
            tool_name="read_github_repo",
            tool_label="Read GitHub Repository",
            args={"github_url": "pallets/flask"},
            tool_call_id="call_123",
        )
        assert pt.tool_name == "read_github_repo"
        assert pt.tool_label == "Read GitHub Repository"
        assert pt.args == {"github_url": "pallets/flask"}
        assert pt.tool_call_id == "call_123"

    def test_pending_tool_default_args(self):
        """PendingTool args should default to empty dict."""
        from api.models import PendingTool

        pt = PendingTool(
            tool_name="create_project",
            tool_label="Create Project",
            tool_call_id="call_456",
        )
        assert pt.args == {}


class TestChatStepResponseModel:
    def test_tool_pending_response(self):
        """ChatStepResponse with status=tool_pending should carry pending_tools and thread_id."""
        from api.models import ChatStepResponse, PendingTool

        resp = ChatStepResponse(
            status="tool_pending",
            thread_id="thread-abc",
            pending_tools=[
                PendingTool(
                    tool_name="read_github_repo",
                    tool_label="Read GitHub Repository",
                    args={"github_url": "pallets/flask"},
                    tool_call_id="call_1",
                ),
            ],
            assistant_message="",
            input_tokens=0,
            output_tokens=0,
        )
        assert resp.status == "tool_pending"
        assert resp.thread_id == "thread-abc"
        assert len(resp.pending_tools) == 1
        assert resp.pending_tools[0].tool_name == "read_github_repo"

    def test_done_response(self):
        """ChatStepResponse with status=done should carry completed_steps and assistant_message."""
        from api.models import ChatStepResponse, ToolStep

        resp = ChatStepResponse(
            status="done",
            thread_id="thread-abc",
            assistant_message="Project created!",
            input_tokens=100,
            output_tokens=50,
            completed_steps=[
                ToolStep(tool_name="create_project", tool_label="Create Project"),
            ],
        )
        assert resp.status == "done"
        assert resp.assistant_message == "Project created!"
        assert len(resp.completed_steps) == 1

    def test_defaults(self):
        """ChatStepResponse defaults should be sensible."""
        from api.models import ChatStepResponse

        resp = ChatStepResponse(
            status="done",
            thread_id="t1",
            assistant_message="Hi",
            input_tokens=0,
            output_tokens=0,
        )
        assert resp.pending_tools == []
        assert resp.completed_steps == []
        assert resp.project_created is None
        assert resp.agent_name == ""
        assert resp.model_name == ""


class TestApproveAndDenyModels:
    def test_approve_request(self):
        """ApproveRequest should accept thread_id."""
        from api.models import ApproveRequest

        req = ApproveRequest(thread_id="thread-abc")
        assert req.thread_id == "thread-abc"

    def test_deny_request_with_default_reason(self):
        """DenyRequest should have a default reason."""
        from api.models import DenyRequest

        req = DenyRequest(thread_id="thread-abc")
        assert req.thread_id == "thread-abc"
        assert req.reason == "Denied by user"

    def test_deny_request_custom_reason(self):
        """DenyRequest should accept a custom reason."""
        from api.models import DenyRequest

        req = DenyRequest(thread_id="thread-abc", reason="Too risky")
        assert req.reason == "Too risky"
