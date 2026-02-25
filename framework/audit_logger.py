"""Structured audit logger — AU-2/AU-3/AU-8/AU-9/AU-12 (NIST 800-53 Rev5).

Every auditable event in the framework flows through AuditLogger.log().
Records are written as JSONL (one JSON object per line) to an append-only
file. Each record contains the mandatory AU-3 fields:
  - event_id        (unique per record)
  - timestamp_utc   (AU-8: UTC, ISO 8601, second precision)
  - session_id      (AU-3: subject identity / session correlation)
  - event_type      (AU-2: one of the defined auditable event types)
  - operator        (AU-3: human identity who started the session, if provided)
  + event-specific context fields (agent_name, tool_name, outcome, etc.)

AU-9 (protection of audit information): the log file is opened in append mode
on each write; the application process never opens it for reading or truncation.
The log directory should be excluded from agent-accessible allowed_paths.

AU-12 (audit record generation): log() is called synchronously at the moment
the event occurs. Failures raise — audit errors are never silently swallowed.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class AuditEventType(str, Enum):
    """AU-2: catalog of auditable events."""
    # Session lifecycle
    SESSION_START       = "SESSION_START"
    SESSION_END         = "SESSION_END"
    # Agent lifecycle
    AGENT_TASK_START    = "AGENT_TASK_START"
    AGENT_TASK_END      = "AGENT_TASK_END"
    # Tool pipeline
    TOOL_CALL_PROPOSED  = "TOOL_CALL_PROPOSED"   # model emitted tool_use block
    VERIFICATION_DECISION = "VERIFICATION_DECISION"  # human approved/denied/edited
    TOOL_EXECUTED       = "TOOL_EXECUTED"         # tool ran, outcome recorded
    TOOL_BLOCKED        = "TOOL_BLOCKED"          # SI-3/SI-10 machine-level block
    TOOL_ACCESS_DENIED  = "TOOL_ACCESS_DENIED"    # AC-3 path violation
    # Multi-agent
    AGENT_HANDOFF       = "AGENT_HANDOFF"
    # MCP
    MCP_CONNECT         = "MCP_CONNECT"
    MCP_CONNECT_FAILED  = "MCP_CONNECT_FAILED"
    # Validation
    VALIDATION_FAILED   = "VALIDATION_FAILED"


class AuditLogger:
    """
    Thread-safe, append-only structured audit logger.

    One instance per session. Created before any agent runs and closed after.
    The log file path is audit_<session_prefix>_<date>.jsonl inside log_dir.
    """

    def __init__(
        self,
        log_dir: str | Path,
        session_id: str,
        operator: str | None = None,
    ):
        self.session_id = session_id
        self.operator = operator

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        self._log_path = self.log_dir / f"audit_{session_id[:8]}_{date_str}.jsonl"
        self._lock = threading.Lock()

        # AU-12: immediately write session start
        self.log(AuditEventType.SESSION_START, operator=operator)

    @property
    def log_path(self) -> Path:
        return self._log_path

    def log(self, event_type: AuditEventType, **kwargs: Any) -> None:
        """
        Write one audit record.

        AU-3 mandatory fields are always present. Caller provides additional
        context via kwargs. None values are omitted to keep records compact.

        AU-12: written and flushed synchronously at event time.
        AU-8:  timestamp is UTC ISO 8601.
        Raises IOError on write failure — must not be silently swallowed.
        """
        record: dict[str, Any] = {
            "event_id":      str(uuid.uuid4()),          # unique record ID
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),  # AU-8
            "session_id":    self.session_id,            # AU-3 subject identity
            "event_type":    event_type.value,           # AU-2 event catalog
        }
        if self.operator:
            record["operator"] = self.operator           # AU-3 human identity

        for k, v in kwargs.items():
            if v is not None:
                record[k] = v

        line = json.dumps(record, default=str)

        # AU-9: open in append mode, flush immediately, never seek/truncate
        with self._lock:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
                # explicit flush — OS buffer flush ensures record is durable
                f.flush()

    def close(self) -> None:
        """Write SESSION_END record. Call in a finally block."""
        self.log(AuditEventType.SESSION_END)
