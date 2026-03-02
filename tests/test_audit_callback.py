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
        handler.on_llm_end(response=mock_response)

        events = _read_events(audit_logger.log_path)
        task_ends = [e for e in events if e["event_type"] == "AGENT_TASK_END"]
        assert len(task_ends) >= 1

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
