"""Session context — AU-2/AU-12 session identity threading (NIST 800-53 Rev5)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class SessionContext:
    """
    Anchors all audit records to a single CLI invocation.

    The session_id ties AGENT_TASK_START → TOOL_CALL_PROPOSED →
    VERIFICATION_DECISION → TOOL_EXECUTED chains together for forensic
    reconstruction (AU-3 content requirements).
    """
    session_id: str
    started_at: str
    operator: str | None


def create_session(operator: str | None = None) -> SessionContext:
    """Create a new session. Call exactly once per CLI invocation (AU-12)."""
    return SessionContext(
        session_id=str(uuid.uuid4()),
        started_at=datetime.now(timezone.utc).isoformat(),
        operator=operator,
    )
