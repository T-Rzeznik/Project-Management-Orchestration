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
    """Point storage at a temp SQLite DB so tests don't touch real data."""
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "test.db")
    storage._init_db()


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

    def test_system_prompt_documents_read_repo_file(self):
        from agents.project_creator import SYSTEM_PROMPT
        assert "read_repo_file" in SYSTEM_PROMPT

    def test_system_prompt_has_file_reading_guidance(self):
        from agents.project_creator import SYSTEM_PROMPT
        prompt_lower = SYSTEM_PROMPT.lower()
        assert "entry point" in prompt_lower or "entry points" in prompt_lower

    def test_system_prompt_requires_file_reading_always(self):
        """File reading should be mandatory, not conditional on README being empty."""
        from agents.project_creator import SYSTEM_PROMPT
        assert "MUST call read_repo_file" in SYSTEM_PROMPT or "ALWAYS call read_repo_file" in SYSTEM_PROMPT


def _mock_agent_done(mock_agent):
    """Configure mock agent's get_state to return done (not interrupted).

    Uses the invoke() return value's messages for get_state().values so
    _build_step_response can extract tool steps and assistant text.
    """
    def _get_state_side_effect(config):
        state = MagicMock()
        state.next = ()
        # Mirror whatever invoke() was set to return
        invoke_result = mock_agent.invoke.return_value
        state.values = {"messages": invoke_result.get("messages", []) if isinstance(invoke_result, dict) else []}
        return state
    mock_agent.get_state.side_effect = _get_state_side_effect


class TestChatToolExecution:
    def test_tool_call_appears_in_response(self):
        """A tool call in LangGraph messages should appear in completed_steps."""
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
            _mock_agent_done(mock_agent)
            mock_get_agent.return_value = mock_agent

            res = client.post("/api/chat", json={
                "messages": [{"role": "user", "content": "Analyze pallets/flask"}],
            })

        assert res.status_code == 200
        data = res.json()
        assert data["assistant_message"] == "I've read the Flask repo!"
        assert len(data["completed_steps"]) == 1
        assert data["completed_steps"][0]["tool_name"] == "read_github_repo"

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
            _mock_agent_done(mock_agent)
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
        """A single tool call should produce one completed_step."""
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
            _mock_agent_done(mock_agent)
            mock_get_agent.return_value = mock_agent

            res = client.post("/api/chat", json={
                "messages": [{"role": "user", "content": "Analyze flask"}],
            })

        data = res.json()
        assert len(data["completed_steps"]) == 1
        step = data["completed_steps"][0]
        assert step["tool_name"] == "read_github_repo"
        assert step["tool_label"] == "Read GitHub Repository"
        assert step["args"] == {"github_url": "pallets/flask"}

    def test_multiple_tool_steps_ordered(self):
        """Multiple tool calls produce ordered completed_steps."""
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
            _mock_agent_done(mock_agent)
            mock_get_agent.return_value = mock_agent

            res = client.post("/api/chat", json={
                "messages": [{"role": "user", "content": "Analyze and create"}],
            })

        data = res.json()
        assert len(data["completed_steps"]) == 2
        assert data["completed_steps"][0]["tool_name"] == "read_github_repo"
        assert data["completed_steps"][1]["tool_name"] == "create_project"

    def test_no_tool_calls_returns_empty_steps(self):
        """A direct text response should have empty completed_steps."""
        result = _make_langgraph_result("Just text")

        with patch("api.server._get_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.invoke.return_value = result
            _mock_agent_done(mock_agent)
            mock_get_agent.return_value = mock_agent

            res = client.post("/api/chat", json={
                "messages": [{"role": "user", "content": "Hello"}],
            })

        data = res.json()
        assert data["completed_steps"] == []

    def test_string_tool_result_preserved_in_detail(self):
        """When a tool returns a plain string (not dict), it should appear in detail."""
        file_content = "import os\nprint('hello')"
        result = _make_langgraph_result(
            "Here's the file content.",
            tool_calls=[{
                "id": "call_1",
                "name": "read_repo_file",
                "args": {"owner": "pallets", "repo": "flask", "path": "app.py"},
                "result": file_content,
            }],
        )

        with patch("api.server._get_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.invoke.return_value = result
            _mock_agent_done(mock_agent)
            mock_get_agent.return_value = mock_agent

            res = client.post("/api/chat", json={
                "messages": [{"role": "user", "content": "Read app.py"}],
            })

        data = res.json()
        step = data["completed_steps"][0]
        assert step["tool_name"] == "read_repo_file"
        # detail should contain the raw string, not empty dict
        assert step["detail"] != {}
        assert "import os" in str(step["detail"])


class TestToolLabel:
    def test_read_github_repo_label(self):
        from api.server import _tool_label
        assert _tool_label("read_github_repo") == "Read GitHub Repository"

    def test_create_project_label(self):
        from api.server import _tool_label
        assert _tool_label("create_project") == "Create Project"

    def test_read_repo_file_label(self):
        from api.server import _tool_label
        assert _tool_label("read_repo_file") == "Read Repository File"

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

    def test_read_repo_file_summary_with_content(self):
        from api.server import _summarize_tool_result
        result = "import os\nimport sys\nprint('hello')"
        summary = _summarize_tool_result("read_repo_file", result)
        assert "34" in summary or "chars" in summary.lower()

    def test_read_repo_file_summary_empty(self):
        from api.server import _summarize_tool_result
        result = ""
        summary = _summarize_tool_result("read_repo_file", result)
        assert "not found" in summary.lower() or "empty" in summary.lower()

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


class TestTokenCounts:
    def test_extracts_from_usage_metadata(self):
        """Gemini puts token counts in AIMessage.usage_metadata, not response_metadata."""
        from api.server import _extract_token_counts

        msg = AIMessage(content="Hello!")
        msg.usage_metadata = {
            "input_tokens": 150,
            "output_tokens": 42,
            "total_tokens": 192,
        }
        input_t, output_t = _extract_token_counts([msg])
        assert input_t == 150
        assert output_t == 42

    def test_sums_across_multiple_messages(self):
        """Token counts should be summed across all AIMessages."""
        from api.server import _extract_token_counts

        msg1 = AIMessage(content="", tool_calls=[{"id": "c1", "name": "t", "args": {}}])
        msg1.usage_metadata = {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}

        msg2 = AIMessage(content="Done!")
        msg2.usage_metadata = {"input_tokens": 200, "output_tokens": 50, "total_tokens": 250}

        input_t, output_t = _extract_token_counts([msg1, msg2])
        assert input_t == 300
        assert output_t == 70

    def test_handles_missing_usage_metadata(self):
        """Messages without usage_metadata should contribute 0."""
        from api.server import _extract_token_counts

        msg = AIMessage(content="Hi")
        # No usage_metadata set
        input_t, output_t = _extract_token_counts([msg])
        assert input_t == 0
        assert output_t == 0

    def test_handles_legacy_response_metadata(self):
        """Should still work if token_usage is in response_metadata (backwards compat)."""
        from api.server import _extract_token_counts

        msg = AIMessage(
            content="Hi",
            response_metadata={"token_usage": {"prompt_tokens": 80, "completion_tokens": 30}},
        )
        input_t, output_t = _extract_token_counts([msg])
        assert input_t == 80
        assert output_t == 30


class TestAssistantMessageExtraction:
    def test_gemini_list_content_with_control_tokens(self):
        """Gemini sometimes returns content as a list with <ctrl42> control tokens.
        These should be sanitized to extract only real text."""
        from api.server import _extract_assistant_message

        messages = [
            AIMessage(
                content=['<ctrl42>', "call\nprint(default_api.read_github_repo(github_url='https://github.com/test/repo'))"],
            ),
        ]
        result = _extract_assistant_message(messages)
        # Should NOT contain control tokens or raw function call syntax
        assert "<ctrl" not in result
        assert "default_api" not in result

    def test_gemini_list_content_extracts_real_text(self):
        """When Gemini returns a list with real text mixed with control tokens,
        the real text should be extracted."""
        from api.server import _extract_assistant_message

        messages = [
            AIMessage(
                content=["Here is the analysis of the repository.", "<ctrl42>"],
            ),
        ]
        result = _extract_assistant_message(messages)
        assert result == "Here is the analysis of the repository."

    def test_gemini_pure_control_token_content_returns_empty(self):
        """If all content parts are control tokens, return empty string."""
        from api.server import _extract_assistant_message

        messages = [
            AIMessage(content=["<ctrl42>"]),
        ]
        result = _extract_assistant_message(messages)
        assert result == ""

    def test_fallback_to_ai_message_with_tool_calls(self):
        """When the only AIMessage with content also has tool_calls, it should still be used."""
        messages = [
            AIMessage(
                content="I've analyzed the repo and created the project.",
                tool_calls=[{
                    "id": "call_1",
                    "name": "create_project",
                    "args": {"name": "Test"},
                }],
                response_metadata={"token_usage": {
                    "prompt_tokens": 10, "completion_tokens": 5,
                }},
            ),
            ToolMessage(
                content="{'status': 'created'}",
                tool_call_id="call_1",
                name="create_project",
            ),
        ]

        with patch("api.server._get_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.invoke.return_value = {"messages": messages}
            _mock_agent_done(mock_agent)
            mock_get_agent.return_value = mock_agent

            with patch("api.server.storage") as mock_storage:
                mock_storage.list_projects.return_value = []
                res = client.post("/api/chat", json={
                    "messages": [{"role": "user", "content": "Analyze repo"}],
                })

        assert res.status_code == 200
        data = res.json()
        assert data["assistant_message"] == "I've analyzed the repo and created the project."


class TestAnalyzeEndpointRemoved:
    def test_post_analyze_returns_404(self):
        """The old POST /api/analyze endpoint should no longer exist."""
        res = client.post("/api/analyze", json={"github_url": "https://github.com/a/b"})
        assert res.status_code in (404, 405)


# --- Thread registry ---


class TestThreadRegistry:
    def test_create_thread_returns_id(self):
        from api.server import _create_thread
        tid = _create_thread()
        assert isinstance(tid, str)
        assert len(tid) > 0

    def test_thread_exists_after_creation(self):
        from api.server import _create_thread, _thread_exists
        tid = _create_thread()
        assert _thread_exists(tid) is True

    def test_thread_not_exists_for_unknown(self):
        from api.server import _thread_exists
        assert _thread_exists("nonexistent-thread-xyz") is False

    def test_cleanup_removes_old_threads(self):
        import time
        from api.server import _create_thread, _thread_exists, _cleanup_threads, _threads
        tid = _create_thread()
        # Manually backdate the thread timestamp
        _threads[tid] = time.time() - 7200  # 2 hours ago
        _cleanup_threads(max_age_seconds=3600)
        assert _thread_exists(tid) is False


# --- Extract pending tools ---


class TestExtractPendingTools:
    def test_extracts_pending_tool_from_ai_message(self):
        from api.server import _extract_pending_tools

        messages = [
            AIMessage(
                content="",
                tool_calls=[{
                    "id": "call_1",
                    "name": "read_github_repo",
                    "args": {"github_url": "pallets/flask"},
                }],
            ),
        ]
        pending = _extract_pending_tools(messages)
        assert len(pending) == 1
        assert pending[0]["tool_name"] == "read_github_repo"
        assert pending[0]["tool_call_id"] == "call_1"
        assert pending[0]["args"] == {"github_url": "pallets/flask"}

    def test_extracts_multiple_pending_tools(self):
        from api.server import _extract_pending_tools

        messages = [
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "call_1", "name": "read_github_repo", "args": {"github_url": "a/b"}},
                    {"id": "call_2", "name": "read_repo_file", "args": {"owner": "a", "repo": "b", "path": "main.py"}},
                ],
            ),
        ]
        pending = _extract_pending_tools(messages)
        assert len(pending) == 2
        assert pending[0]["tool_name"] == "read_github_repo"
        assert pending[1]["tool_name"] == "read_repo_file"

    def test_returns_empty_when_no_tool_calls(self):
        from api.server import _extract_pending_tools

        messages = [
            AIMessage(content="Just text, no tools."),
        ]
        pending = _extract_pending_tools(messages)
        assert pending == []

    def test_uses_last_ai_message_with_tool_calls(self):
        """Should find pending tools from the LAST AIMessage with tool_calls."""
        from api.server import _extract_pending_tools

        messages = [
            AIMessage(
                content="",
                tool_calls=[{"id": "call_old", "name": "read_github_repo", "args": {}}],
            ),
            ToolMessage(content="result", tool_call_id="call_old", name="read_github_repo"),
            AIMessage(
                content="",
                tool_calls=[{"id": "call_new", "name": "create_project", "args": {"name": "X"}}],
            ),
        ]
        pending = _extract_pending_tools(messages)
        assert len(pending) == 1
        assert pending[0]["tool_name"] == "create_project"
        assert pending[0]["tool_call_id"] == "call_new"


# --- Step-by-step chat endpoint ---


class TestStepByStepChat:
    def test_chat_returns_tool_pending_on_interrupt(self):
        """POST /api/chat should return status=tool_pending when agent interrupts."""
        mock_agent = MagicMock()
        pending_messages = [
            AIMessage(
                content="",
                tool_calls=[{
                    "id": "call_1",
                    "name": "read_github_repo",
                    "args": {"github_url": "pallets/flask"},
                }],
            ),
        ]
        mock_agent.invoke.return_value = {"messages": pending_messages}
        # get_state().next indicates interrupted
        mock_state = MagicMock()
        mock_state.next = ("tools",)
        mock_state.values = {"messages": pending_messages}
        mock_agent.get_state.return_value = mock_state

        with patch("api.server._get_agent", return_value=mock_agent):
            res = client.post("/api/chat", json={
                "messages": [{"role": "user", "content": "Analyze pallets/flask"}],
            })

        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "tool_pending"
        assert data["thread_id"]  # should have a thread ID
        assert len(data["pending_tools"]) == 1
        assert data["pending_tools"][0]["tool_name"] == "read_github_repo"

    def test_chat_returns_done_when_no_interrupt(self):
        """POST /api/chat should return status=done when agent completes."""
        mock_agent = MagicMock()
        done_messages = [
            AIMessage(
                content="Hello! How can I help?",
                response_metadata={"token_usage": {"prompt_tokens": 10, "completion_tokens": 5}},
            ),
        ]
        mock_agent.invoke.return_value = {"messages": done_messages}
        mock_state = MagicMock()
        mock_state.next = ()  # no interrupt
        mock_state.values = {"messages": done_messages}
        mock_agent.get_state.return_value = mock_state

        with patch("api.server._get_agent", return_value=mock_agent):
            res = client.post("/api/chat", json={
                "messages": [{"role": "user", "content": "Hello"}],
            })

        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "done"
        assert data["assistant_message"] == "Hello! How can I help?"
        assert data["pending_tools"] == []


class TestApproveEndpoint:
    def test_approve_resumes_agent(self):
        """POST /api/chat/approve should resume the agent and return next state."""
        from api.server import _create_thread, _threads

        thread_id = _create_thread()

        approve_messages = [
            AIMessage(
                content="",
                tool_calls=[{"id": "call_1", "name": "read_github_repo", "args": {}}],
                response_metadata={"token_usage": {"prompt_tokens": 5, "completion_tokens": 3}},
            ),
            ToolMessage(content="{'owner': 'a', 'repo': 'b'}", tool_call_id="call_1", name="read_github_repo"),
            AIMessage(
                content="Done analyzing!",
                response_metadata={"token_usage": {"prompt_tokens": 10, "completion_tokens": 5}},
            ),
        ]

        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"messages": approve_messages}
        mock_state = MagicMock()
        mock_state.next = ()
        mock_state.values = {"messages": approve_messages}
        mock_agent.get_state.return_value = mock_state

        with patch("api.server._get_agent", return_value=mock_agent):
            res = client.post("/api/chat/approve", json={"thread_id": thread_id})

        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "done"
        assert data["assistant_message"] == "Done analyzing!"

    def test_approve_unknown_thread_returns_404(self):
        """POST /api/chat/approve with unknown thread should return 404."""
        res = client.post("/api/chat/approve", json={"thread_id": "nonexistent"})
        assert res.status_code == 404


class TestDenyEndpoint:
    def test_deny_injects_denial_and_resumes(self):
        """POST /api/chat/deny should inject denial messages and resume."""
        from api.server import _create_thread

        thread_id = _create_thread()

        mock_agent = MagicMock()

        # get_state before deny — the agent has pending tool calls
        pending_state = MagicMock()
        pending_state.next = ("tools",)
        pending_state.values = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[{"id": "call_1", "name": "read_github_repo", "args": {}}],
                ),
            ],
        }

        # After update_state + invoke, agent responds with adapted message
        deny_result_messages = [
            AIMessage(
                content="",
                tool_calls=[{"id": "call_1", "name": "read_github_repo", "args": {}}],
            ),
            ToolMessage(content="Denied by user", tool_call_id="call_1", name="read_github_repo"),
            AIMessage(
                content="I understand, the tool was denied. How else can I help?",
                response_metadata={"token_usage": {"prompt_tokens": 10, "completion_tokens": 8}},
            ),
        ]
        done_state = MagicMock()
        done_state.next = ()
        done_state.values = {"messages": deny_result_messages}
        # get_state is called 3 times: (1) pending tool extraction, (2) full_messages in _deny_and_resume, (3) _build_step_response
        mock_agent.get_state.side_effect = [pending_state, done_state, done_state]

        mock_agent.invoke.return_value = {"messages": deny_result_messages}

        with patch("api.server._get_agent", return_value=mock_agent):
            res = client.post("/api/chat/deny", json={
                "thread_id": thread_id,
                "reason": "Too risky",
            })

        assert res.status_code == 200
        data = res.json()
        # Agent should have called update_state
        mock_agent.update_state.assert_called_once()

    def test_deny_unknown_thread_returns_404(self):
        """POST /api/chat/deny with unknown thread should return 404."""
        res = client.post("/api/chat/deny", json={"thread_id": "nonexistent"})
        assert res.status_code == 404
