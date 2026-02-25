"""Verify-then-commit gate — AU-2/AU-3/AU-12/SC-28/SI-10 (NIST 800-53 Rev5).

Every tool call emits two audit events:
  1. TOOL_CALL_PROPOSED  — written before showing anything to the operator (AU-12)
  2. VERIFICATION_DECISION — written after the operator responds (y/n/e)

The console panel shows REAL (unscrubbed) args to the operator — they are
an authorized reviewer who needs accurate information. The AUDIT LOG receives
scrubbed args only (SC-28: protect data at rest).

After human edits ([e] path), edited args are re-validated against the tool's
declared input_schema before acceptance (SI-10).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import jsonschema
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from framework.audit_logger import AuditEventType
from framework.secret_scrubber import scrub_dict

if TYPE_CHECKING:
    from framework.audit_logger import AuditLogger

console = Console()


@dataclass
class VerificationResult:
    approved: bool
    input: dict[str, Any] = field(default_factory=dict)


class VerificationGate:
    """
    Interactive gate that surfaces every tool call to the operator for review.

    AU-2/AU-12: emits audit records before and after the human decision.
    SC-28:      args are scrubbed before being written to the audit log.
    SI-10:      edited args are re-validated against the tool's input_schema.
    """

    def __init__(
        self,
        mode: str = "always",
        require_for: list[str] | None = None,
        audit_logger: "AuditLogger | None" = None,
        tool_schemas: list[dict] | None = None,
    ):
        self.mode = mode
        self.require_for: set[str] = set(require_for or [])
        self._audit = audit_logger
        # Map tool_name → schema for post-edit validation (SI-10)
        self._schemas: dict[str, dict] = {
            s["name"]: s for s in (tool_schemas or [])
        }

    def update_schemas(self, schemas: list[dict]) -> None:
        """Update known tool schemas (called after MCP tools are discovered)."""
        for s in schemas:
            self._schemas[s["name"]] = s

    def _needs_verification(self, tool_name: str) -> bool:
        if self.mode == "always":
            return True
        if self.mode == "never":
            return False
        return tool_name in self.require_for

    def prompt(
        self,
        agent_name: str,
        tool_name: str,
        tool_input: dict[str, Any],
        model: str | None = None,
    ) -> VerificationResult:
        """Show tool call to operator and collect approval / denial / edit."""

        # AU-12: emit TOOL_CALL_PROPOSED before showing to human
        scrubbed_input = scrub_dict(tool_input)   # SC-28
        if self._audit:
            self._audit.log(
                AuditEventType.TOOL_CALL_PROPOSED,
                agent_name=agent_name,
                model=model,
                tool_name=tool_name,
                tool_input_scrubbed=scrubbed_input,
            )

        if not self._needs_verification(tool_name):
            if self._audit:
                self._audit.log(
                    AuditEventType.VERIFICATION_DECISION,
                    agent_name=agent_name,
                    tool_name=tool_name,
                    verification_choice="auto_approved",
                    outcome="approved",
                )
            return VerificationResult(approved=True, input=tool_input)

        # Display REAL args to the authorized operator (not scrubbed)
        args_json = json.dumps(tool_input, indent=2)
        console.print(
            Panel(
                f"[bold cyan]{agent_name}[/bold cyan] wants to call: "
                f"[bold yellow]{tool_name}[/bold yellow]\n\n"
                + Syntax(args_json, "json", theme="monokai", word_wrap=True).highlight(args_json),
                title="[bold red]Tool Call Verification[/bold red]",
                border_style="yellow",
            )
        )

        choice = ""
        approved = False
        final_input = tool_input

        while True:
            try:
                raw = input("  [y] Approve  [n] Deny  [e] Edit args > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                console.print("\n[red]Interrupted — denying tool call.[/red]")
                choice = "interrupted"
                approved = False
                break

            if raw == "y":
                choice = "y"
                approved = True
                break

            if raw == "n":
                choice = "n"
                approved = False
                console.print("[red]Tool call denied.[/red]")
                break

            if raw == "e":
                edited = self._edit_args(tool_input)
                # SI-10: re-validate edited args against declared schema
                schema = self._schemas.get(tool_name)
                if schema:
                    try:
                        from framework.input_validator import validate_tool_args
                        validate_tool_args(tool_name, edited, schema)
                    except jsonschema.ValidationError as exc:
                        console.print(
                            f"[red]Edited args failed schema validation: {exc.message}\n"
                            "Please edit again or choose [n] to deny.[/red]"
                        )
                        continue  # let operator try again

                # Show edited args and confirm
                edited_json = json.dumps(edited, indent=2)
                console.print(
                    Panel(
                        Syntax(edited_json, "json", theme="monokai", word_wrap=True).highlight(edited_json),
                        title="[bold green]Edited Args — Confirm?[/bold green]",
                        border_style="green",
                    )
                )
                try:
                    confirm = input("  [y] Approve edited  [n] Deny > ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    choice = "interrupted"
                    approved = False
                    break

                if confirm == "y":
                    choice = "e"
                    approved = True
                    final_input = edited
                    break
                if confirm == "n":
                    choice = "n"
                    approved = False
                    break
            else:
                console.print("[dim]Please enter y, n, or e.[/dim]")

        # AU-12: emit VERIFICATION_DECISION after human responds
        if self._audit:
            self._audit.log(
                AuditEventType.VERIFICATION_DECISION,
                agent_name=agent_name,
                model=model,
                tool_name=tool_name,
                verification_choice=choice,
                tool_input_scrubbed=scrub_dict(final_input),  # SC-28
                outcome="approved" if approved else "denied",
            )

        return VerificationResult(approved=approved, input=final_input)

    def _edit_args(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Let operator paste new JSON args."""
        console.print("[cyan]Enter new JSON args (blank line twice to finish):[/cyan]")
        lines: list[str] = []
        try:
            while True:
                line = input()
                if line == "" and lines and lines[-1] == "":
                    break
                lines.append(line)
        except (EOFError, KeyboardInterrupt):
            console.print("[yellow]Edit cancelled — keeping original args.[/yellow]")
            return tool_input

        raw = "\n".join(lines).strip()
        if not raw:
            return tool_input
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            console.print(f"[red]Invalid JSON: {exc}. Keeping original args.[/red]")
            return tool_input
