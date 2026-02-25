"""Built-in bash tool — AC-6/SI-3/SI-10 (NIST 800-53 Rev5).

The bash tool enforces two layers of control before any subprocess is spawned:
  1. SI-3: machine-level command blocklist (cannot be overridden by human approval)
  2. SI-10: input size and timeout caps

The subprocess always runs with cwd set to the first allowed root (AC-6).
The human verification gate is an additional control on top of these.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from framework.input_validator import (
    validate_bash_command,
    validate_bash_timeout,
)

if TYPE_CHECKING:
    from framework.path_enforcer import PathEnforcer


def make_bash_function(path_enforcer: "PathEnforcer") -> dict:
    """
    Return a bash callable bound to the given PathEnforcer.

    The subprocess cwd is set to the first allowed root (AC-6 least privilege).
    """

    def bash(command: str, timeout: int = 60) -> str:
        """
        Run a shell command and return stdout + stderr.

        SI-3: command is checked against the blocklist before execution.
        SI-10: timeout is capped; command length is validated.
        AC-6: working directory is confined to the first allowed root.
        """
        # SI-3 / SI-10: machine-level validation before human gate and subprocess
        validate_bash_command(command)
        safe_timeout = validate_bash_timeout(timeout)

        # AC-6: confine working directory to first allowed root
        cwd = str(path_enforcer.allowed_roots[0]) if path_enforcer.allowed_roots else None

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=safe_timeout,
                cwd=cwd,
            )
            output_parts = []
            if result.stdout:
                output_parts.append(result.stdout)
            if result.stderr:
                output_parts.append(f"[stderr]\n{result.stderr}")
            if result.returncode != 0:
                output_parts.append(f"[exit code: {result.returncode}]")
            return "\n".join(output_parts) if output_parts else "(no output)"
        except subprocess.TimeoutExpired:
            return f"Error: command timed out after {safe_timeout}s"
        except Exception as exc:
            return f"Error running command: {exc}"

    return {"bash": bash}


BASH_TOOL_SCHEMA: dict = {
    "name": "bash",
    "description": (
        "Run a shell command. Always requires user verification. "
        "Dangerous patterns are blocked unconditionally by security policy."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute"},
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (max 300, default 60)",
                "default": 60,
            },
        },
        "required": ["command"],
    },
}
