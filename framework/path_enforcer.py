"""Path traversal prevention — AC-3, AC-6, AU-9 (NIST 800-53 Rev5).

Enforces that all file-system operations are confined to declared allowed roots
and never touch protected directories (e.g. the audit log directory).
"""

from __future__ import annotations

import os
from pathlib import Path


class PathEnforcer:
    """
    Confines agent file access to declared allowed roots.

    Controls:
      AC-3  — Access enforcement: deny operations outside allowed scope.
      AC-6  — Least privilege: agent can only access what is explicitly allowed.
      AU-9  — Protection of audit info: audit log dir is always in protected_dirs.
    """

    def __init__(
        self,
        allowed_roots: list[str | Path],
        protected_dirs: list[str | Path] | None = None,
    ):
        """
        Args:
            allowed_roots: Directories the agent may read/write.
            protected_dirs: Directories NEVER accessible, even if inside an
                            allowed root. Used to protect audit logs (AU-9).
        """
        if not allowed_roots:
            raise ValueError("PathEnforcer requires at least one allowed_root.")

        self.allowed_roots: list[Path] = []
        for r in allowed_roots:
            p = Path(r).resolve()
            if not p.exists():
                raise ValueError(f"AC-6: allowed_root does not exist: {r}")
            if not p.is_dir():
                raise ValueError(f"AC-6: allowed_root is not a directory: {r}")
            self.allowed_roots.append(p)

        self.protected_dirs: list[Path] = []
        for d in (protected_dirs or []):
            self.protected_dirs.append(Path(d).resolve())

    def check(self, path: str | Path, operation: str = "access") -> Path:
        """
        Validate that path is within an allowed root and not in a protected dir.

        Returns the resolved Path if allowed.
        Raises PermissionError with an audit-friendly message if denied.
        """
        try:
            resolved = Path(path).resolve()
        except Exception as exc:
            raise PermissionError(
                f"AC-3: Invalid path for '{operation}': {exc}"
            ) from exc

        # AU-9: block access to protected directories (e.g. audit log dir)
        for protected in self.protected_dirs:
            if resolved == protected or _is_relative_to(resolved, protected):
                raise PermissionError(
                    f"AC-3/AU-9: '{operation}' denied — '{resolved}' is inside "
                    f"protected directory '{protected}'"
                )

        # AC-3: must resolve inside at least one allowed root
        for root in self.allowed_roots:
            if _is_relative_to(resolved, root):
                return resolved

        roots_str = ", ".join(f"'{r}'" for r in self.allowed_roots)
        raise PermissionError(
            f"AC-3: '{operation}' denied — '{resolved}' is outside allowed "
            f"paths: [{roots_str}]"
        )

    @classmethod
    def from_config(
        cls,
        allowed_paths: list[str] | None,
        protected_dirs: list[str | Path] | None = None,
    ) -> "PathEnforcer":
        """
        Build from agent YAML config. Falls back to CWD when list is empty.
        CWD fallback is logged as a warning via the caller.
        """
        if not allowed_paths:
            allowed_paths = [os.getcwd()]
        return cls(allowed_roots=allowed_paths, protected_dirs=protected_dirs)


def _is_relative_to(path: Path, parent: Path) -> bool:
    """Portable Path.is_relative_to (backport for Python < 3.9)."""
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
