"""Tool registry — AC-6, AU-12 (NIST 800-53 Rev5).

Tool functions are instantiated via factory functions (not at import time) so
that each agent gets callables bound to its own PathEnforcer (AC-6 least
privilege). ToolRegistry.call() differentiates between normal errors, AC-3
path violations, and SI-3/SI-10 machine-level blocks so each maps to a
distinct audit event type.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from tools.bash_tool import BASH_TOOL_SCHEMA, make_bash_function
from tools.file_tools import FILE_TOOL_SCHEMAS, make_file_functions
from tools.web_tools import WEB_TOOL_SCHEMA, make_web_function

if TYPE_CHECKING:
    from framework.audit_logger import AuditLogger
    from framework.path_enforcer import PathEnforcer

# Static schema list — used to enumerate available tool names without a PathEnforcer
_STATIC_SCHEMAS: dict[str, dict] = {
    s["name"]: s for s in FILE_TOOL_SCHEMAS
}
_STATIC_SCHEMAS[BASH_TOOL_SCHEMA["name"]] = BASH_TOOL_SCHEMA
_STATIC_SCHEMAS[WEB_TOOL_SCHEMA["name"]] = WEB_TOOL_SCHEMA

AVAILABLE_BUILTIN_TOOLS: list[str] = list(_STATIC_SCHEMAS.keys())


class ToolRegistry:
    """Holds the set of built-in tools enabled for a specific agent instance."""

    def __init__(
        self,
        enabled_tools: list[str] | None = None,
        path_enforcer: "PathEnforcer | None" = None,
        audit_logger: "AuditLogger | None" = None,
    ):
        if enabled_tools is None:
            enabled_tools = []

        # Validate names early
        unknown = [n for n in enabled_tools if n not in _STATIC_SCHEMAS]
        if unknown:
            raise ValueError(
                f"Unknown built-in tool(s): {unknown}. "
                f"Available: {AVAILABLE_BUILTIN_TOOLS}"
            )

        # Build per-agent bound callables via factory functions (AC-6)
        if path_enforcer is None:
            from framework.path_enforcer import PathEnforcer
            path_enforcer = PathEnforcer.from_config([])

        all_fns: dict[str, Callable] = {
            **make_file_functions(path_enforcer),
            **make_bash_function(path_enforcer),
            **make_web_function(),
        }

        self.schemas: list[dict] = []
        self.functions: dict[str, Callable] = {}

        for name in enabled_tools:
            self.schemas.append(_STATIC_SCHEMAS[name])
            self.functions[name] = all_fns[name]

        self._audit = audit_logger

    def add_tool(self, schema: dict, fn: Callable) -> None:
        """Register an extra tool (e.g. delegate_to_agent injected by Orchestrator)."""
        self.schemas.append(schema)
        self.functions[schema["name"]] = fn

    def call(self, name: str, args: dict[str, Any]) -> str:
        """
        Execute a built-in tool by name.

        Exceptions are mapped to audit outcomes:
          PermissionError  → TOOL_ACCESS_DENIED  (AC-3)
          ValueError       → TOOL_BLOCKED        (SI-3/SI-10)
          Other            → TOOL_EXECUTED with outcome=error
        """
        from framework.audit_logger import AuditEventType

        if name not in self.functions:
            return f"Error: unknown tool '{name}'"

        try:
            return self.functions[name](**args)

        except PermissionError as exc:
            # AC-3: path outside allowed roots
            if self._audit:
                self._audit.log(
                    AuditEventType.TOOL_ACCESS_DENIED,
                    tool_name=name,
                    outcome="access_denied",
                    detail=str(exc),
                )
            return f"Access denied: {exc}"

        except ValueError as exc:
            # SI-3/SI-10: machine-level block (blocklist, size limit, SSRF)
            if self._audit:
                self._audit.log(
                    AuditEventType.TOOL_BLOCKED,
                    tool_name=name,
                    outcome="blocked",
                    detail=str(exc),
                )
            return f"Tool call blocked by security policy: {exc}"

        except TypeError as exc:
            return f"Error calling tool '{name}': {exc}"

        except Exception as exc:
            return f"Tool '{name}' raised an error: {exc}"

    def get_schemas(self) -> list[dict]:
        """Return Anthropic-formatted tool schemas for this registry."""
        return list(self.schemas)
