"""Orchestrator — wires all components and runs tasks (NIST 800-53 Rev5).

Security responsibilities:
  AU-2/AU-3/AU-12: Creates the AuditLogger and threads it through every Agent
                   and VerificationGate instance.
  AC-3/AC-6:       Builds a PathEnforcer from each agent's allowed_paths config
                   with the audit log directory in protected_dirs (AU-9).
  SC-28:           MCP env blocks (which may contain credentials) are never
                   included in audit records.
  CM-6:            Validates agent config against schema before use, including
                   the FedRAMP High policy check (no 'never' mode for high-risk tools).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console

import anthropic
from framework.agent import Agent
from framework.audit_logger import AuditEventType, AuditLogger
from framework.mcp_client import MCPClientManager
from framework.path_enforcer import PathEnforcer
from framework.schema import check_high_risk_never_mode, validate_agent_config
from framework.tool_registry import ToolRegistry
from framework.verification import VerificationGate

console = Console()

DELEGATE_TOOL_SCHEMA: dict = {
    "name": "delegate_to_agent",
    "description": (
        "Delegate a subtask to a specialized agent. "
        "Returns the agent's final response as a string."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "agent": {
                "type": "string",
                "description": "Name of the agent to delegate to",
            },
            "task": {
                "type": "string",
                "description": "Clear description of the subtask",
            },
            "context": {
                "type": "string",
                "description": "Relevant context to pass to the sub-agent",
            },
        },
        "required": ["agent", "task"],
    },
}


class Orchestrator:
    """Loads agents from YAML, wires security components, and runs tasks."""

    def __init__(
        self,
        agents_dir: str | Path = "agents",
        audit_logger: AuditLogger | None = None,
    ):
        self.agents_dir = Path(agents_dir)
        self._configs: dict[str, dict] = {}
        self._yaml_paths: dict[str, Path] = {}
        self._anthropic_client = anthropic.Anthropic()
        self._audit = audit_logger

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------

    def load_agent_file(self, yaml_path: str | Path) -> dict:
        """Load, validate, and cache a single agent YAML file."""
        p = Path(yaml_path)
        if not p.exists():
            raise FileNotFoundError(f"Agent YAML not found: {yaml_path}")

        with open(p, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        validate_agent_config(config)
        check_high_risk_never_mode(config)   # FedRAMP High policy (CM-6)

        name = config["name"]
        self._configs[name] = config
        self._yaml_paths[name] = p
        return config

    def load_agents_dir(self) -> None:
        """Load all *.yaml files from the agents directory."""
        if not self.agents_dir.exists():
            return
        for yaml_path in sorted(self.agents_dir.glob("*.yaml")):
            try:
                self.load_agent_file(yaml_path)
                console.print(f"[dim]Loaded agent: {yaml_path.name}[/dim]")
            except Exception as exc:
                console.print(
                    f"[yellow]Warning: failed to load {yaml_path.name}: {exc}[/yellow]"
                )

    # ------------------------------------------------------------------
    # Agent instantiation
    # ------------------------------------------------------------------

    def build_agent(self, config: dict) -> Agent:
        """Instantiate an Agent with all security components wired (AC-3/AC-6/AU)."""
        name = config["name"]
        audit_cfg = config.get("audit", {})

        # Determine audit log directory — used for AU-9 protected_dirs
        audit_log_dir = Path(
            audit_cfg.get("log_dir")
            or (self._audit.log_dir if self._audit else ".audit_logs")
        ).resolve()

        # AC-3/AC-6: build PathEnforcer from config, protecting audit log dir
        allowed_paths = config.get("allowed_paths", [])
        if not allowed_paths:
            console.print(
                f"[yellow]Warning (AC-6): agent '{name}' has no allowed_paths — "
                "defaulting to CWD. Add allowed_paths in YAML for least-privilege "
                "path confinement.[/yellow]"
            )
        path_enforcer = PathEnforcer.from_config(
            allowed_paths=allowed_paths,
            protected_dirs=[audit_log_dir],   # AU-9: agent cannot touch audit logs
        )

        # Verification gate (injects AuditLogger for AU-12 events)
        verification_cfg = config.get("verification", {})
        gate = VerificationGate(
            mode=verification_cfg.get("mode", "always"),
            require_for=verification_cfg.get("require_for", []),
            audit_logger=self._audit,
        )

        # Built-in tool registry (AC-6: only listed tools are enabled)
        enabled_builtins: list[str] = config.get("tools", {}).get("builtin", [])
        registry = ToolRegistry(
            enabled_tools=enabled_builtins,
            path_enforcer=path_enforcer,
            audit_logger=self._audit,
        )

        # Handoff tool injection
        handoff_cfg = config.get("handoff", {})
        can_delegate_to: list[str] = handoff_cfg.get("can_delegate_to", [])
        if can_delegate_to:
            registry.add_tool(
                schema=DELEGATE_TOOL_SCHEMA,
                fn=self._make_delegate_fn(name, can_delegate_to),
            )

        # MCP connections (SC-28: env blocks logged without values)
        mcp_configs: list[dict] = config.get("tools", {}).get("mcp", [])
        mcp_manager = MCPClientManager()
        if mcp_configs:
            console.print(f"[dim]Connecting MCP servers for agent '{name}'...[/dim]")
            mcp_manager.connect_all(mcp_configs, audit_logger=self._audit)

        return Agent(
            config=config,
            tool_registry=registry,
            mcp_manager=mcp_manager,
            verification_gate=gate,
            anthropic_client=self._anthropic_client,
            audit_logger=self._audit,
        )

    def _make_delegate_fn(self, parent_name: str, allowed: list[str]):
        """Create the delegate_to_agent callable for handoff (AU-2: logs AGENT_HANDOFF)."""
        orch = self

        def delegate_to_agent(agent: str, task: str, context: str = "") -> str:
            if agent not in allowed:
                return (
                    f"Error: agent '{agent}' not in allowed delegation list: {allowed}"
                )
            if agent not in orch._configs:
                candidate = orch.agents_dir / f"{agent}.yaml"
                if candidate.exists():
                    orch.load_agent_file(candidate)
                else:
                    return f"Error: agent '{agent}' YAML not found."

            # AU-12: log handoff before sub-agent runs
            if orch._audit:
                orch._audit.log(
                    AuditEventType.AGENT_HANDOFF,
                    agent_name=parent_name,
                    outcome=f"delegating_to:{agent}",
                    tool_name="delegate_to_agent",
                    task_summary=task[:200],
                )

            console.print(
                f"[bold blue]Handoff:[/bold blue] {parent_name} → {agent}"
            )
            sub_config = orch._configs[agent]
            sub_agent = orch.build_agent(sub_config)
            try:
                return sub_agent.run(task=task, context=context)
            finally:
                sub_agent.mcp_manager.shutdown()

        return delegate_to_agent

    # ------------------------------------------------------------------
    # Public run API
    # ------------------------------------------------------------------

    def run_task(self, agent_name: str, task: str, context: str = "") -> str:
        """Run a task on a named (already loaded) agent."""
        if agent_name not in self._configs:
            raise ValueError(
                f"Agent '{agent_name}' not loaded. Call load_agent_file() first."
            )
        config = self._configs[agent_name]
        agent = self.build_agent(config)
        try:
            return agent.run(task=task, context=context)
        finally:
            agent.mcp_manager.shutdown()

    def run_from_yaml(self, yaml_path: str | Path, task: str, context: str = "") -> str:
        """Load a YAML file and immediately run a task on it."""
        config = self.load_agent_file(yaml_path)
        agent = self.build_agent(config)
        try:
            return agent.run(task=task, context=context)
        finally:
            agent.mcp_manager.shutdown()
