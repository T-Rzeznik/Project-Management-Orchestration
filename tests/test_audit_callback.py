"""Tests for the LangChain audit callback handler."""

import json
from unittest.mock import MagicMock, patch

import pytest

from security.audit_callback import AuditCallbackHandler
from framework.audit_logger import AuditEventType


@pytest.fixture
def audit_logger(tmp_path):
    from framework.audit_logger import AuditLogger
    return AuditLogger(log_dir=tmp_path, session_id="test-session", operator="tester")


@pytest.fixture
def handler(audit_logger):
    return AuditCallbackHandler(audit_logger=audit_logger, agent_name="project_creator")


class TestAuditCallbackHandler:
    def test_on_llm_start_logs_agent_task_start(self, handler, audit_logger):
        handler.on_llm_start(serialized={}, prompts=["Hello"])

        events = _read_events(audit_logger.log_path)
        task_starts = [e for e in events if e["event_type"] == "AGENT_TASK_START"]
        assert len(task_starts) >= 1
        assert task_starts[0]["agent_name"] == "project_creator"

    def test_on_chat_model_start_logs_agent_task_start(self, handler, audit_logger):
        """Chat models (Gemini, OpenAI gpt-*) dispatch on_chat_model_start, not on_llm_start."""
        import uuid as _uuid
        from langchain_core.messages import HumanMessage

        handler.on_chat_model_start(
            serialized={},
            messages=[[HumanMessage(content="Hi")]],
            run_id=_uuid.uuid4(),
        )

        events = _read_events(audit_logger.log_path)
        task_starts = [e for e in events if e["event_type"] == "AGENT_TASK_START"]
        assert len(task_starts) >= 1
        assert task_starts[0]["agent_name"] == "project_creator"

    def test_on_tool_start_logs_tool_call_proposed(self, handler, audit_logger):
        handler.on_tool_start(
            serialized={},
            input_str="",
            name="read_github_repo",
            tool_input={"github_url": "pallets/flask"},
        )

        events = _read_events(audit_logger.log_path)
        proposed = [e for e in events if e["event_type"] == "TOOL_CALL_PROPOSED"]
        assert len(proposed) == 1
        assert proposed[0]["tool_name"] == "read_github_repo"

    def test_on_tool_end_logs_tool_executed(self, handler, audit_logger):
        handler.on_tool_end(output="some result", name="read_github_repo")

        events = _read_events(audit_logger.log_path)
        executed = [e for e in events if e["event_type"] == "TOOL_EXECUTED"]
        assert len(executed) == 1
        assert executed[0]["tool_name"] == "read_github_repo"

    def test_on_tool_error_logs_tool_blocked(self, handler, audit_logger):
        handler.on_tool_error(
            error=ValueError("bad input"),
            name="read_github_repo",
        )

        events = _read_events(audit_logger.log_path)
        blocked = [e for e in events if e["event_type"] == "TOOL_BLOCKED"]
        assert len(blocked) == 1
        assert blocked[0]["tool_name"] == "read_github_repo"
        assert "bad input" in blocked[0]["detail"]

    def test_on_llm_end_logs_agent_task_end(self, handler, audit_logger):
        mock_response = MagicMock()
        mock_response.llm_output = {
            "token_usage": {"prompt_tokens": 100, "completion_tokens": 50}
        }
        mock_response.generations = []
        handler.on_llm_end(response=mock_response)

        events = _read_events(audit_logger.log_path)
        task_ends = [e for e in events if e["event_type"] == "AGENT_TASK_END"]
        assert len(task_ends) >= 1

    def test_on_llm_end_captures_openai_style_token_usage(self, handler, audit_logger):
        """OpenAI-style llm_output.token_usage should be recorded in totals."""
        mock_response = MagicMock()
        mock_response.llm_output = {
            "token_usage": {"prompt_tokens": 100, "completion_tokens": 50}
        }
        mock_response.generations = []
        handler.on_llm_end(response=mock_response)

        events = _read_events(audit_logger.log_path)
        task_ends = [e for e in events if e["event_type"] == "AGENT_TASK_END"]
        assert task_ends[-1]["total_input_tokens"] == 100
        assert task_ends[-1]["total_output_tokens"] == 50

    def test_on_llm_end_captures_gemini_usage_metadata(self, handler, audit_logger):
        """Gemini stores token counts on AIMessage.usage_metadata across generations."""
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatGeneration, LLMResult

        msg = AIMessage(
            content="hi",
            usage_metadata={
                "input_tokens": 200,
                "output_tokens": 75,
                "total_tokens": 275,
            },
        )
        result = LLMResult(
            generations=[[ChatGeneration(message=msg)]],
            llm_output=None,
        )

        handler.on_llm_end(response=result)

        events = _read_events(audit_logger.log_path)
        task_ends = [e for e in events if e["event_type"] == "AGENT_TASK_END"]
        assert task_ends[-1]["total_input_tokens"] == 200
        assert task_ends[-1]["total_output_tokens"] == 75

    def test_on_llm_end_sums_across_multiple_generations(self, handler, audit_logger):
        """Multiple AIMessage generations should be summed."""
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatGeneration, LLMResult

        m1 = AIMessage(
            content="a",
            usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        )
        m2 = AIMessage(
            content="b",
            usage_metadata={"input_tokens": 20, "output_tokens": 8, "total_tokens": 28},
        )
        result = LLMResult(
            generations=[[ChatGeneration(message=m1)], [ChatGeneration(message=m2)]],
            llm_output=None,
        )

        handler.on_llm_end(response=result)

        events = _read_events(audit_logger.log_path)
        task_ends = [e for e in events if e["event_type"] == "AGENT_TASK_END"]
        assert task_ends[-1]["total_input_tokens"] == 30
        assert task_ends[-1]["total_output_tokens"] == 13

    def test_scrubs_secrets_from_tool_args(self, handler, audit_logger):
        handler.on_tool_start(
            serialized={},
            input_str="",
            name="some_tool",
            tool_input={"api_key": "sk-ant-secret123456789012345"},
        )

        events = _read_events(audit_logger.log_path)
        proposed = [e for e in events if e["event_type"] == "TOOL_CALL_PROPOSED"]
        assert len(proposed) == 1
        # The api_key value should be redacted
        assert "sk-ant-" not in json.dumps(proposed[0])


def _read_events(log_path) -> list[dict]:
    events = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


class TestCallbackPropagationThroughReactAgent:
    """End-to-end: verify the AuditCallbackHandler actually fires when passed
    via config to a real LangGraph create_react_agent. This guards against
    regressions like the one where on_chat_model_start was missing and no
    events past SESSION_START were ever written."""

    def test_callbacks_fire_for_chat_model_and_tools(self, tmp_path):
        from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
        from langchain_core.messages import AIMessage
        from langchain_core.tools import tool
        from langgraph.prebuilt import create_react_agent

        from framework.audit_logger import AuditLogger
        from security.audit_callback import AuditCallbackHandler

        logger = AuditLogger(log_dir=tmp_path, session_id="propagation-test")
        handler = AuditCallbackHandler(audit_logger=logger, agent_name="project_creator")

        @tool
        def echo_tool(text: str) -> str:
            """Echo the input back."""
            return f"echoed:{text}"

        # First model turn: request a tool call. Second turn: finish with text.
        scripted = iter([
            AIMessage(
                content="",
                tool_calls=[{
                    "id": "call-1",
                    "name": "echo_tool",
                    "args": {"text": "hi"},
                }],
            ),
            AIMessage(content="all done"),
        ])

        class _ToolBindingFakeChat(GenericFakeChatModel):
            """GenericFakeChatModel that satisfies create_react_agent's bind_tools check."""

            def bind_tools(self, tools, **kwargs):
                return self

        fake_model = _ToolBindingFakeChat(messages=scripted)

        agent = create_react_agent(model=fake_model, tools=[echo_tool])
        agent.invoke(
            {"messages": [("user", "kick off")]},
            config={"callbacks": [handler]},
        )

        events = _read_events(logger.log_path)
        event_types = [e["event_type"] for e in events]

        assert "AGENT_TASK_START" in event_types, (
            f"Chat-model start hook never fired. Got: {event_types}"
        )
        assert "TOOL_CALL_PROPOSED" in event_types, (
            f"Tool start hook never fired. Got: {event_types}"
        )
        assert "TOOL_EXECUTED" in event_types, (
            f"Tool end hook never fired. Got: {event_types}"
        )
        assert "AGENT_TASK_END" in event_types, (
            f"LLM end hook never fired. Got: {event_types}"
        )

        named = [e for e in events if e.get("agent_name")]
        assert named, "No event ever recorded an agent_name"
        assert all(e["agent_name"] == "project_creator" for e in named)
