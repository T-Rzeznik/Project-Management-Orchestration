"""YAML agent schema validation — CM-6, SI-10 (NIST 800-53 Rev5)."""

import jsonschema

AGENT_SCHEMA = {
    "type": "object",
    "required": ["name", "model", "system_prompt"],
    "properties": {
        "name":         {"type": "string"},
        "description":  {"type": "string"},
        "model":        {"type": "string"},
        "system_prompt": {"type": "string"},
        # AU-3: human identity who configured/runs this agent
        "operator":     {"type": "string"},
        "tools": {
            "type": "object",
            "properties": {
                "builtin": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "mcp": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["name", "transport", "command"],
                        "properties": {
                            "name":      {"type": "string"},
                            "transport": {"type": "string", "enum": ["stdio", "sse"]},
                            "command":   {"type": "string"},
                            "args":      {"type": "array", "items": {"type": "string"}},
                            "url":       {"type": "string"},
                            "env":       {"type": "object"},
                        },
                    },
                },
            },
        },
        "verification": {
            "type": "object",
            "properties": {
                "mode":        {"type": "string", "enum": ["always", "selective", "never"]},
                "require_for": {"type": "array", "items": {"type": "string"}},
            },
        },
        "max_turns": {"type": "integer", "minimum": 1},
        "handoff": {
            "type": "object",
            "properties": {
                "can_delegate_to": {"type": "array", "items": {"type": "string"}},
            },
        },
        # AC-3/AC-6: filesystem path confinement (FedRAMP High)
        "allowed_paths": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Filesystem paths the agent may read/write. "
                "Defaults to CWD if omitted (logged as a warning). "
                "Must not include the audit log directory (AU-9)."
            ),
        },
        # AU-2/AU-3: audit log configuration
        "audit": {
            "type": "object",
            "properties": {
                "log_dir": {
                    "type": "string",
                    "description": "Directory for audit JSONL files. Default: .audit_logs/",
                },
                "max_result_chars": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 2000,
                    "description": "Max chars of tool result to include in audit record.",
                },
            },
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}


def validate_agent_config(config: dict) -> None:
    """Validate agent YAML config. Raises jsonschema.ValidationError on failure."""
    jsonschema.validate(instance=config, schema=AGENT_SCHEMA)


def get_verification_mode(config: dict) -> str:
    """Return the verification mode, defaulting to 'always'."""
    return config.get("verification", {}).get("mode", "always")


def check_high_risk_never_mode(config: dict) -> None:
    """
    Enforce that high-risk tools cannot run with verification mode 'never'.

    FedRAMP High requires human review for destructive operations.
    Raises ValueError if the configuration would allow unreviewed bash or write_file.
    """
    mode = get_verification_mode(config)
    if mode != "never":
        return

    HIGH_RISK_TOOLS = {"bash", "write_file"}
    enabled = set(config.get("tools", {}).get("builtin", []))
    violations = HIGH_RISK_TOOLS & enabled
    if violations:
        raise ValueError(
            f"FedRAMP High policy violation: verification mode 'never' is not "
            f"permitted when high-risk tools are enabled: {sorted(violations)}. "
            "Use 'always' or 'selective' mode."
        )
