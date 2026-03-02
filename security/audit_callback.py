"""LangChain callback handler for FedRAMP audit logging (AU-2/AU-3/AU-12)."""

from __future__ import annotations

from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from framework.audit_logger import AuditEventType, AuditLogger
from framework.secret_scrubber import scrub_dict


class AuditCallbackHandler(BaseCallbackHandler):
    """Maps LangChain lifecycle events to FedRAMP audit events.

    Uses the existing ``AuditLogger`` and ``secret_scrubber`` so all
    NIST 800-53 controls (AU-2, AU-3, AU-8, AU-9, AU-12, SC-28) are
    preserved through the LangChain migration.
    """

    def __init__(self, audit_logger: AuditLogger, agent_name: str = ""):
        super().__init__()
        self._logger = audit_logger
        self._agent_name = agent_name

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
        self._logger.log(
            AuditEventType.AGENT_TASK_START,
            agent_name=self._agent_name,
        )

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        name: str | None = None,
        tool_input: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        scrubbed_args = scrub_dict(tool_input) if tool_input else {}
        self._logger.log(
            AuditEventType.TOOL_CALL_PROPOSED,
            agent_name=self._agent_name,
            tool_name=name or "",
            tool_args=scrubbed_args,
        )

    def on_tool_end(
        self,
        output: str,
        *,
        name: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._logger.log(
            AuditEventType.TOOL_EXECUTED,
            agent_name=self._agent_name,
            tool_name=name or "",
            outcome="success",
        )

    def on_tool_error(
        self,
        error: BaseException,
        *,
        name: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._logger.log(
            AuditEventType.TOOL_BLOCKED,
            agent_name=self._agent_name,
            tool_name=name or "",
            detail=str(error),
        )

    def on_llm_end(
        self,
        response: LLMResult,
        **kwargs: Any,
    ) -> None:
        token_usage = {}
        if response.llm_output and isinstance(response.llm_output, dict):
            token_usage = response.llm_output.get("token_usage", {})

        self._logger.log(
            AuditEventType.AGENT_TASK_END,
            agent_name=self._agent_name,
            total_input_tokens=token_usage.get("prompt_tokens", 0),
            total_output_tokens=token_usage.get("completion_tokens", 0),
        )
