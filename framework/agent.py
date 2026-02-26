"""Agent agentic loop — AU-2/AU-3/AU-12 (NIST 800-53 Rev5).

Audit events emitted by this module:
  AGENT_TASK_START      — at the beginning of run()
  TOOL_EXECUTED         — after each tool call completes (approved path)
  AGENT_TASK_END        — when the loop exits (end_turn or max_turns)

Tool call proposals and verification decisions are audited by VerificationGate.
Tool-level blocks (AC-3, SI-3/SI-10) are audited by ToolRegistry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from framework.audit_logger import AuditEventType
from framework.providers.base import (
    NormalizedTextBlock,
    NormalizedToolUseBlock,
)
from framework.secret_scrubber import scrub_dict, scrub_string

if TYPE_CHECKING:
    from framework.audit_logger import AuditLogger
    from framework.mcp_client import MCPClientManager
    from framework.providers.base import BaseProvider
    from framework.tool_registry import ToolRegistry
    from framework.verification import VerificationGate

console = Console()

# Max chars of tool result written to audit log (AU-3: avoid logging bulk secrets)
_AUDIT_RESULT_MAX_CHARS = 500


class Agent:
    """An agent that runs an agentic loop with tool use and verification."""

    def __init__(
        self,
        config: dict,
        tool_registry: "ToolRegistry",
        mcp_manager: "MCPClientManager",
        verification_gate: "VerificationGate",
        provider: "BaseProvider | None" = None,
        audit_logger: "AuditLogger | None" = None,
    ):
        self.config = config
        self.name: str = config["name"]
        self.model: str = config["model"]
        self.system_prompt: str = config["system_prompt"]
        self.max_turns: int = config.get("max_turns", 20)

        self.tool_registry = tool_registry
        self.mcp_manager = mcp_manager
        self.gate = verification_gate
        if provider is None:
            from framework.providers.anthropic_provider import AnthropicProvider
            provider = AnthropicProvider()
        self.provider = provider
        self._audit = audit_logger

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    def _all_tool_schemas(self) -> list[dict]:
        """Combine built-in + MCP tool schemas for the Anthropic API."""
        return self.tool_registry.get_schemas() + self.mcp_manager.all_tools()

    def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Execute a tool (builtin or MCP) — already verified by caller."""
        if tool_name in self.tool_registry.functions:
            return self.tool_registry.call(tool_name, tool_input)
        return self.mcp_manager.call_tool(tool_name, tool_input)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self, task: str, context: str = "") -> str:
        """Run the agent on a task, returning the final text response."""

        # AU-12: AGENT_TASK_START before any work begins
        if self._audit:
            self._audit.log(
                AuditEventType.AGENT_TASK_START,
                agent_name=self.name,
                model=self.model,
                task_summary=scrub_string(task[:300]),
            )

        console.print(
            Panel(
                f"[bold]{self.name}[/bold] starting task:\n{task}",
                title=f"[cyan]Agent: {self.name}[/cyan]",
                border_style="cyan",
            )
        )

        user_content = task
        if context:
            user_content = f"Context:\n{context}\n\nTask:\n{task}"

        messages: list[dict] = [{"role": "user", "content": user_content}]
        tools = self._all_tool_schemas()

        # Let the verification gate know about all tool schemas for SI-10 re-validation
        self.gate.update_schemas(tools)

        turn = 0
        final_text = ""

        try:
            while turn < self.max_turns:
                turn += 1
                console.print(f"[dim][{self.name}] Turn {turn}/{self.max_turns}[/dim]")

                response = self.provider.create_message(
                    model=self.model,
                    system=self.system_prompt,
                    messages=messages,
                    tools=tools,
                    max_tokens=8096,
                )

                messages.append({
                    "role": "assistant",
                    "content": [b.to_dict() for b in response.content],
                })

                if response.stop_reason == "end_turn":
                    final_text = self._extract_text(response.content)
                    console.print(
                        Panel(
                            Markdown(final_text) if final_text else "[dim](no text response)[/dim]",
                            title=f"[green]{self.name} — Final Response[/green]",
                            border_style="green",
                        )
                    )
                    break

                if response.stop_reason == "tool_use":
                    tool_results = self._handle_tool_use_blocks(response.content)
                    messages.append({"role": "user", "content": tool_results})
                    continue

                console.print(
                    f"[yellow]Unexpected stop_reason: {response.stop_reason}. Stopping.[/yellow]"
                )
                break

            else:
                console.print(
                    f"[yellow][{self.name}] Reached max_turns ({self.max_turns}).[/yellow]"
                )
                final_text = self._extract_text(messages[-1].get("content", []))

        finally:
            # AU-12: AGENT_TASK_END always written, even on exception
            if self._audit:
                self._audit.log(
                    AuditEventType.AGENT_TASK_END,
                    agent_name=self.name,
                    model=self.model,
                    turns_used=turn,
                    outcome="completed",
                )

        return final_text

    def _handle_tool_use_blocks(self, content: list) -> list[dict]:
        """Process all tool_use blocks, verify each, and return tool_result list."""
        results = []

        for block in content:
            if block.type != "tool_use":
                continue

            tool_name = block.name
            tool_input = block.input or {}

            console.print(
                f"\n[bold magenta]→ Tool call:[/bold magenta] [yellow]{tool_name}[/yellow]"
            )

            # Verification gate emits TOOL_CALL_PROPOSED + VERIFICATION_DECISION (AU-12)
            verification = self.gate.prompt(
                self.name, tool_name, tool_input, model=self.model
            )

            if not verification.approved:
                tool_result_content = "User denied this tool call."
                console.print(f"[red]  Denied: {tool_name}[/red]")
            else:
                approved_input = verification.input
                console.print(f"[green]  Executing: {tool_name}[/green]")
                tool_result_content = self._execute_tool(tool_name, approved_input)

                # AU-12: TOOL_EXECUTED after successful dispatch
                # SC-28: scrub args and truncate result before writing to audit log
                if self._audit:
                    result_summary = scrub_string(
                        str(tool_result_content)[:_AUDIT_RESULT_MAX_CHARS]
                    )
                    self._audit.log(
                        AuditEventType.TOOL_EXECUTED,
                        agent_name=self.name,
                        model=self.model,
                        tool_name=tool_name,
                        tool_input_scrubbed=scrub_dict(approved_input),
                        outcome="success",
                        result_summary=result_summary,
                    )

            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(tool_result_content),
                }
            )

        return results

    def _extract_text(self, content: Any) -> str:
        """Extract all text blocks from a message content list."""
        if isinstance(content, str):
            return content
        parts = []
        for block in content:
            if hasattr(block, "type") and block.type == "text":
                parts.append(block.text)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block["text"])
        return "\n".join(parts)
