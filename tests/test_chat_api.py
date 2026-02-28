"""Tests for the AI chat endpoint and models."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.models import ChatMessage, ChatRequest, ChatResponse
from api.server import app


# --- Phase 1: Model validation tests ---


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
        """Empty content is allowed (Anthropic API handles it)."""
        msg = ChatMessage(role="user", content="")
        assert msg.content == ""


class TestChatRequest:
    def test_valid_request(self):
        req = ChatRequest(
            messages=[ChatMessage(role="user", content="Hello")]
        )
        assert len(req.messages) == 1
        assert req.model == "gemini-2.5-flash-lite"

    def test_empty_messages_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(messages=[])

    def test_custom_model(self):
        req = ChatRequest(
            messages=[ChatMessage(role="user", content="Hi")],
            model="claude-haiku-4-5-20251001",
        )
        assert req.model == "claude-haiku-4-5-20251001"


class TestChatResponse:
    def test_valid_response(self):
        resp = ChatResponse(
            assistant_message="Hello!", input_tokens=10, output_tokens=5
        )
        assert resp.assistant_message == "Hello!"
        assert resp.input_tokens == 10
        assert resp.output_tokens == 5


# --- Phase 2: Endpoint tests ---

client = TestClient(app)


def _mock_genai():
    """Create a mock google.generativeai module returning a canned response."""
    mock_response = MagicMock()
    mock_response.text = "Hello from AI!"
    mock_response.usage_metadata.prompt_token_count = 15
    mock_response.usage_metadata.candidates_token_count = 8

    mock_model_instance = MagicMock()
    mock_model_instance.generate_content.return_value = mock_response

    mock_genai = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model_instance
    return mock_genai


class TestChatEndpoint:
    def test_valid_chat_returns_200(self):
        mock_g = _mock_genai()
        with patch("api.server._get_chat_provider", return_value=mock_g):
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

    def test_full_history_forwarded_to_provider(self):
        mock_g = _mock_genai()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you?"},
        ]
        with patch("api.server._get_chat_provider", return_value=mock_g):
            client.post("/api/chat", json={"messages": messages})

        model_inst = mock_g.GenerativeModel.return_value
        call_args = model_inst.generate_content.call_args
        contents = call_args[0][0]
        assert len(contents) == 3
        assert contents[0] == {"role": "user", "parts": ["Hello"]}
        assert contents[1] == {"role": "model", "parts": ["Hi there"]}
        assert contents[2] == {"role": "user", "parts": ["How are you?"]}

    def test_provider_exception_returns_500(self):
        mock_g = MagicMock()
        mock_g.GenerativeModel.return_value.generate_content.side_effect = RuntimeError("API down")
        with patch("api.server._get_chat_provider", return_value=mock_g):
            res = client.post("/api/chat", json={
                "messages": [{"role": "user", "content": "Hi"}],
            })
        assert res.status_code == 500
        assert "API down" in res.json()["detail"]
