"""Tests for the AI chat endpoint and models."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.models import ChatMessage, ChatRequest, ChatResponse, ToolStep
from api.server import app


# --- Phase 1: Model validation tests (unchanged — no mocking needed) ---


class TestChatMessage:
    def test_user_role_accepted(self):
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_assistant_role_accepted(self):
        msg = ChatMessage(role="assistant", content="Hi there")
        assert msg.role == "assistant"

    def test_invalid_role_rejected(self):
        with pytest.raises(ValidationError):
            ChatMessage(role="system", content="bad")

    def test_empty_content_accepted(self):
        msg = ChatMessage(role="user", content="")
        assert msg.content == ""


class TestChatRequest:
    def test_valid_request(self):
        req = ChatRequest(
            messages=[ChatMessage(role="user", content="Hello")]
        )
        assert len(req.messages) == 1
        assert req.model == "gemini-2.5-flash"

    def test_empty_messages_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(messages=[])

    def test_custom_model(self):
        req = ChatRequest(
            messages=[ChatMessage(role="user", content="Hi")],
            model="gemini-2.0-flash",
        )
        assert req.model == "gemini-2.0-flash"


class TestToolStep:
    def test_tool_step_fields(self):
        step = ToolStep(
            tool_name="read_github_repo",
            tool_label="Read GitHub Repository",
            args={"github_url": "pallets/flask"},
            summary="Fetched pallets/flask",
            detail={"owner": "pallets"},
            duration_ms=123,
        )
        assert step.tool_name == "read_github_repo"
        assert step.tool_label == "Read GitHub Repository"
        assert step.args == {"github_url": "pallets/flask"}
        assert step.summary == "Fetched pallets/flask"
        assert step.detail == {"owner": "pallets"}
        assert step.duration_ms == 123


class TestChatResponse:
    def test_valid_response(self):
        resp = ChatResponse(
            assistant_message="Hello!", input_tokens=10, output_tokens=5
        )
        assert resp.assistant_message == "Hello!"
        assert resp.input_tokens == 10
        assert resp.output_tokens == 5

    def test_response_defaults_empty_tool_steps(self):
        resp = ChatResponse(
            assistant_message="Hi", input_tokens=1, output_tokens=1
        )
        assert resp.tool_steps == []

    def test_response_with_tool_steps(self):
        step = ToolStep(
            tool_name="read_github_repo",
            tool_label="Read GitHub Repository",
            args={"github_url": "pallets/flask"},
            summary="Fetched pallets/flask",
            detail={"stars": 65000},
            duration_ms=200,
        )
        resp = ChatResponse(
            assistant_message="Done",
            input_tokens=10,
            output_tokens=5,
            tool_steps=[step],
        )
        assert len(resp.tool_steps) == 1
        assert resp.tool_steps[0].tool_name == "read_github_repo"

    def test_response_accepts_agent_name_and_model_name(self):
        resp = ChatResponse(
            assistant_message="Hi",
            input_tokens=10,
            output_tokens=5,
            agent_name="project_creator",
            model_name="gemini-2.5-flash",
        )
        assert resp.agent_name == "project_creator"
        assert resp.model_name == "gemini-2.5-flash"

    def test_response_defaults_agent_name_empty(self):
        resp = ChatResponse(
            assistant_message="Hi", input_tokens=1, output_tokens=1
        )
        assert resp.agent_name == ""
        assert resp.model_name == ""


# --- Phase 2: Endpoint tests (mock LangGraph agent) ---

client = TestClient(app)


def _make_langgraph_result(text: str, tool_calls=None, input_tokens=15, output_tokens=8):
    """Build a mock LangGraph agent.invoke() result (dict with 'messages' key)."""
    from langchain_core.messages import AIMessage, ToolMessage

    messages = []

    if tool_calls:
        for tc in tool_calls:
            # AI message with tool call
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
            # Tool result message
            tool_msg = ToolMessage(
                content=str(tc.get("result", {})),
                tool_call_id=tc.get("id", "call_1"),
                name=tc["name"],
            )
            messages.append(tool_msg)

    # Final AI text response
    final_msg = AIMessage(
        content=text,
        response_metadata={"token_usage": {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
        }},
    )
    messages.append(final_msg)

    return {"messages": messages}


def _mock_agent_done(mock_agent):
    """Configure mock agent's get_state to indicate graph completed (not interrupted)."""
    def _get_state_side_effect(config):
        state = MagicMock()
        state.next = ()
        invoke_result = mock_agent.invoke.return_value
        state.values = {"messages": invoke_result.get("messages", []) if isinstance(invoke_result, dict) else []}
        return state
    mock_agent.get_state.side_effect = _get_state_side_effect


class TestChatEndpoint:
    def test_valid_chat_returns_200(self):
        result = _make_langgraph_result("Hello from AI!")
        with patch("api.server._get_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.invoke.return_value = result
            _mock_agent_done(mock_agent)
            mock_get_agent.return_value = mock_agent

            res = client.post("/api/chat", json={
                "messages": [{"role": "user", "content": "Hi"}],
            })
        assert res.status_code == 200
        data = res.json()
        assert data["assistant_message"] == "Hello from AI!"
        assert data["input_tokens"] == 15
        assert data["output_tokens"] == 8

    def test_empty_messages_returns_422(self):
        res = client.post("/api/chat", json={"messages": []})
        assert res.status_code == 422

    def test_response_includes_agent_name_and_model_name(self):
        result = _make_langgraph_result("Hi!")
        with patch("api.server._get_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.invoke.return_value = result
            _mock_agent_done(mock_agent)
            mock_get_agent.return_value = mock_agent

            res = client.post("/api/chat", json={
                "messages": [{"role": "user", "content": "Hi"}],
            })
        data = res.json()
        assert data["agent_name"] == "project_creator"
        assert data["model_name"] == "gemini-2.5-flash"

    def test_provider_exception_returns_500(self):
        with patch("api.server._get_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.invoke.side_effect = RuntimeError("API down")
            mock_get_agent.return_value = mock_agent

            res = client.post("/api/chat", json={
                "messages": [{"role": "user", "content": "Hi"}],
            })
        assert res.status_code == 500
        assert "API down" in res.json()["detail"]
