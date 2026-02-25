"""Built-in file system tools — AC-3/AC-6/SI-10 (NIST 800-53 Rev5).

Tool functions are returned by make_file_functions(), which binds a PathEnforcer
so that every file operation is confined to declared allowed roots (AC-3/AC-6).
Schemas are static and safe to import at module level.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from framework.input_validator import check_content_size

if TYPE_CHECKING:
    from framework.path_enforcer import PathEnforcer


def make_file_functions(path_enforcer: "PathEnforcer") -> dict:
    """
    Return file tool callables bound to the given PathEnforcer.

    The returned functions raise PermissionError (caught by ToolRegistry)
    for any path outside the enforcer's allowed roots.
    """

    def read_file(path: str) -> str:
        """Read a file. Path must resolve inside an allowed root (AC-3)."""
        resolved = path_enforcer.check(path, operation="read")
        if not resolved.exists():
            return f"Error: file not found: {path}"
        if not resolved.is_file():
            return f"Error: not a file: {path}"
        try:
            return resolved.read_text(encoding="utf-8")
        except Exception as exc:
            return f"Error reading file: {exc}"

    def write_file(path: str, content: str) -> str:
        """Write content to a file. Path must resolve inside an allowed root (AC-3)."""
        check_content_size(content, "content")           # SI-10: size cap
        resolved = path_enforcer.check(path, operation="write")
        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, encoding="utf-8")
            return f"Successfully wrote {len(content)} chars to {path}"
        except PermissionError:
            raise   # propagate path enforcer PermissionErrors
        except Exception as exc:
            return f"Error writing file: {exc}"

    def list_dir(path: str = ".") -> str:
        """List directory contents. Path must resolve inside an allowed root (AC-3)."""
        resolved = path_enforcer.check(path, operation="list")
        if not resolved.exists():
            return f"Error: path not found: {path}"
        if not resolved.is_dir():
            return f"Error: not a directory: {path}"
        try:
            entries = sorted(resolved.iterdir(), key=lambda e: (e.is_file(), e.name))
            lines = []
            for entry in entries:
                if entry.is_dir():
                    lines.append(f"[DIR]  {entry.name}/")
                else:
                    size = entry.stat().st_size
                    lines.append(f"[FILE] {entry.name} ({size} bytes)")
            return "\n".join(lines) if lines else "(empty directory)"
        except Exception as exc:
            return f"Error listing directory: {exc}"

    return {
        "read_file": read_file,
        "write_file": write_file,
        "list_dir": list_dir,
    }


# Anthropic tool schemas — static, no PathEnforcer needed
FILE_TOOL_SCHEMAS: list[dict] = [
    {
        "name": "read_file",
        "description": "Read the contents of a file at the given path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative file path"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file. Creates parent directories if needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative file path"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_dir",
        "description": "List the contents of a directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path (default: current directory)",
                },
            },
            "required": [],
        },
    },
]
