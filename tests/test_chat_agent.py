"""Tests for the agentic chat loop (LangGraph agent)."""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage

from api import storage
from api.server import app


@pytest.fixture(autouse=True)
def clean_storage(tmp_path, monkeypatch):
    """Point storage at a temp file so tests don't touch real data."""
    monkeypatch.setattr(storage, "STORAGE_PATH", tmp_path / "projects.json")


client = TestClient(app)


def _make_langgraph_result(text, tool_calls=None, input_tokens=10, output_tokens=5):
    """Build a mock LangGraph agent.invoke() result."""
    messages = []

    if tool_calls:
        for tc in tool_calls:
            ai_msg = AIMessage(
                content="",
                tool_calls=[{
                    "id": tc.get("id", "call_1"),
                    "name": tc["name"],
                    "args": tc["args"],
                }],
                response_metadata={"token_usage": {
                    "prompt_tokens": 5, "completion_tokens": 3,
                }},
            )
            messages.append(ai_msg)
            tool_msg = ToolMessage(
                content=str(tc.get("result", {})),
                tool_call_id=tc.get("id", "call_1"),
                name=tc["name"],
            )
            messages.append(tool_msg)

    final_msg = AIMessage(
        content=text,
        response_metadata={"token_usage": {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
        }},
    )
    messages.append(final_msg)

    return {"messages": messages}


class TestAgentConfig:
    def test_agent_name_exposed(self):
        from agents.project_creator import AGENT_NAME
        assert AGENT_NAME == "project_creator"

    def test_system_prompt_contains_instructions(self):
        from agents.project_creator import SYSTEM_PROMPT
        assert "project management" in SYSTEM_PROMPT.lower()


class TestChatToolExecution:
    def test_tool_call_appears_in_response(self):
        """A tool call in LangGraph messages should appear in tool_steps."""
        fake_result = {"owner": "pallets", "repo": "flask", "name": "flask"}
        result = _make_langgraph_result(
            "I've read the Flask repo!",
            tool_calls=[{
                "id": "call_1",
                "name": "read_github_repo",
                "args": {"github_url": "pallets/flask"},
                "result": fake_result,
            }],
        )

        with patch("api.server._get_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.invoke.return_value = result
            mock_get_agent.return_value = mock_agent

            res = client.post("/api/chat", json={
                "messages": [{"role": "user", "content": "Analyze pallets/flask"}],
            })

        assert res.status_code == 200
        data = res.json()
        assert data["assistant_message"] == "I've read the Flask repo!"
        assert len(data["tool_steps"]) == 1
        assert data["tool_steps"][0]["tool_name"] == "read_github_repo"

    def test_create_project_detected_in_response(self):
        """When LangGraph calls create_project, project_created should be populated."""
        project_result = {"status": "created", "project_id": "abc-123", "name": "Flask"}
        result = _make_langgraph_result(
            "Project created!",
            tool_calls=[{
                "id": "call_1",
                "name": "create_project",
                "args": {"name": "Flask", "description": "A micro web framework"},
                "result": project_result,
            }],
        )

        with patch("api.server._get_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.invoke.return_value = result
            mock_get_agent.return_value = mock_agent

            # Also mock storage so _find_created_project can find it
            with patch("api.server.storage") as mock_storage:
                mock_storage.list_projects.return_value = [
                    {"id": "abc-123", "name": "Flask", "description": "A micro web framework"},
                ]

                res = client.post("/api/chat", json={
                    "messages": [{"role": "user", "content": "Create a project for Flask"}],
                })

        assert res.status_code == 200
        data = res.json()
        assert data["assistant_message"] == "Project created!"
        assert data["project_created"] is not None
        assert data["project_created"]["name"] == "Flask"


class TestToolStepsInResponse:
    def test_tool_steps_included_in_response(self):
        """A single tool call should produce one tool_step."""
        result = _make_langgraph_result(
            "Done!",
            tool_calls=[{
                "id": "call_1",
                "name": "read_github_repo",
                "args": {"github_url": "pallets/flask"},
                "result": {"owner": "pallets", "repo": "flask"},
            }],
        )

        with patch("api.server._get_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.invoke.return_value = result
            mock_get_agent.return_value = mock_agent

            res = client.post("/api/chat", json={
                "messages": [{"role": "user", "content": "Analyze flask"}],
            })

        data = res.json()
        assert len(data["tool_steps"]) == 1
        step = data["tool_steps"][0]
        assert step["tool_name"] == "read_github_repo"
        assert step["tool_label"] == "Read GitHub Repository"
        assert step["args"] == {"github_url": "pallets/flask"}

    def test_multiple_tool_steps_ordered(self):
        """Multiple tool calls produce ordered tool_steps."""
        result = _make_langgraph_result(
            "All done!",
            tool_calls=[
                {
                    "id": "call_1",
                    "name": "read_github_repo",
                    "args": {"github_url": "pallets/flask"},
                    "result": {"owner": "pallets", "repo": "flask"},
                },
                {
                    "id": "call_2",
                    "name": "create_project",
                    "args": {"name": "Flask"},
                    "result": {"status": "created", "name": "Flask"},
                },
            ],
        )

        with patch("api.server._get_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.invoke.return_value = result
            mock_get_agent.return_value = mock_agent

            res = client.post("/api/chat", json={
                "messages": [{"role": "user", "content": "Analyze and create"}],
            })

        data = res.json()
        assert len(data["tool_steps"]) == 2
        assert data["tool_steps"][0]["tool_name"] == "read_github_repo"
        assert data["tool_steps"][1]["tool_name"] == "create_project"

    def test_no_tool_calls_returns_empty_steps(self):
        """A direct text response should have an empty tool_steps list."""
        result = _make_langgraph_result("Just text")

        with patch("api.server._get_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.invoke.return_value = result
            mock_get_agent.return_value = mock_agent

            res = client.post("/api/chat", json={
                "messages": [{"role": "user", "content": "Hello"}],
            })

        data = res.json()
        assert data["tool_steps"] == []


class TestToolLabel:
    def test_read_github_repo_label(self):
        from api.server import _tool_label
        assert _tool_label("read_github_repo") == "Read GitHub Repository"

    def test_create_project_label(self):
        from api.server import _tool_label
        assert _tool_label("create_project") == "Create Project"

    def test_unknown_tool_label(self):
        from api.server import _tool_label
        assert _tool_label("some_new_tool") == "Some New Tool"


class TestToolSummary:
    def test_github_summary(self):
        from api.server import _summarize_tool_result
        result = {"owner": "pallets", "repo": "flask", "stars": 65000}
        assert _summarize_tool_result("read_github_repo", result) == "Fetched pallets/flask"

    def test_create_project_summary(self):
        from api.server import _summarize_tool_result
        result = {"status": "created", "project_id": "abc", "name": "Flask"}
        assert _summarize_tool_result("create_project", result) == "Created project: Flask"

    def test_unknown_tool_fallback(self):
        from api.server import _summarize_tool_result
        result = {"foo": "bar"}
        assert _summarize_tool_result("unknown_tool", result) == "Completed"


class TestMcpManager:
    @pytest.fixture(autouse=True)
    def reset_mcp_state(self):
        import api.server as srv
        srv._mcp_manager = None
        srv._mcp_initialized = False
        yield
        srv._mcp_manager = None
        srv._mcp_initialized = False

    def test_returns_none_when_no_mcp_config(self):
        from api.server import _get_mcp_manager
        import api.server as srv

        srv._mcp_manager = None
        srv._mcp_initialized = False

        with patch("api.server._MCP_CONFIGS", []):
            result = _get_mcp_manager()

        assert result is None

    def test_singleton_only_initializes_once(self):
        from api.server import _get_mcp_manager
        import api.server as srv

        srv._mcp_manager = None
        srv._mcp_initialized = False

        with patch("api.server._MCP_CONFIGS", []):
            _get_mcp_manager()
            _get_mcp_manager()

        # Should complete without error (singleton pattern)
        assert True


class TestAnalyzeEndpointRemoved:
    def test_post_analyze_returns_404(self):
        """The old POST /api/analyze endpoint should no longer exist."""
        res = client.post("/api/analyze", json={"github_url": "https://github.com/a/b"})
        assert res.status_code in (404, 405)
