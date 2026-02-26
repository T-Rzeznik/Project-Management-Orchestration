"""CLI entry point — AU-2/AU-3/AU-12 session anchoring (NIST 800-53 Rev5).

The session is created here, once per CLI invocation, before any agent runs.
AuditLogger is created from the session and passed into the Orchestrator.
The audit log path is printed to the operator at startup.

--operator flag (AU-3): identifies the human running the session for attribution
in audit records. Optional but recommended for FedRAMP High environments.
"""

from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(
    name="orchestration-framework",
    help=(
        "YAML-based AI agent orchestration framework with verify-then-commit "
        "tool gates and FedRAMP High audit controls."
    ),
    add_completion=False,
)
console = Console()


def _audit_log_dir() -> Path:
    """Return the audit log directory from env var or default."""
    return Path(os.environ.get("AUDIT_LOG_DIR", ".audit_logs"))


def _create_session_and_logger(operator: str | None):
    """Create a session and AuditLogger. Returns (session, logger)."""
    from framework.audit_logger import AuditLogger
    from framework.session import create_session

    session = create_session(operator=operator)
    log_dir = _audit_log_dir()
    logger = AuditLogger(
        log_dir=log_dir,
        session_id=session.session_id,
        operator=operator,
    )
    console.print(
        f"[dim]Session: {session.session_id[:8]}…  "
        f"Audit log: {logger.log_path}[/dim]"
    )
    return session, logger


def _get_orchestrator(audit_logger=None):
    from framework.orchestrator import Orchestrator
    return Orchestrator(agents_dir="agents", audit_logger=audit_logger)


@app.command()
def run(
    agent_yaml: str = typer.Argument(..., help="Path to agent YAML file"),
    task: str = typer.Argument(..., help="Task description for the agent"),
    context: str = typer.Option("", "--context", "-c", help="Optional context string"),
    operator: str = typer.Option(
        None, "--operator", "-o",
        help="AU-3: human identity running this session (for audit attribution)",
    ),
):
    """Run a single agent on a task."""
    session, audit = _create_session_and_logger(operator)
    orch = _get_orchestrator(audit)
    try:
        result = orch.run_from_yaml(agent_yaml, task=task, context=context)
    except FileNotFoundError as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"[red]Fatal error: {exc}[/red]")
        raise typer.Exit(1)
    finally:
        audit.close()

    console.print(Panel(result, title="[green]Final Result[/green]", border_style="green"))


@app.command()
def orchestrate(
    orchestrator_yaml: str = typer.Argument(..., help="Path to orchestrator agent YAML"),
    task: str = typer.Argument(..., help="High-level task for the orchestrator"),
    context: str = typer.Option("", "--context", "-c", help="Optional context string"),
    operator: str = typer.Option(
        None, "--operator", "-o",
        help="AU-3: human identity running this session",
    ),
):
    """Start a multi-agent workflow via an orchestrator agent."""
    session, audit = _create_session_and_logger(operator)
    orch = _get_orchestrator(audit)
    orch.load_agents_dir()
    try:
        result = orch.run_from_yaml(orchestrator_yaml, task=task, context=context)
    except FileNotFoundError as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"[red]Fatal error: {exc}[/red]")
        raise typer.Exit(1)
    finally:
        audit.close()

    console.print(Panel(result, title="[green]Final Result[/green]", border_style="green"))


@app.command()
def chat(
    agent_yaml: str = typer.Argument(..., help="Path to agent YAML file"),
    operator: str = typer.Option(
        None, "--operator", "-o",
        help="AU-3: human identity running this session",
    ),
):
    """Interactive chat session with an agent."""
    from framework.orchestrator import Orchestrator

    session, audit = _create_session_and_logger(operator)
    orch = Orchestrator(agents_dir="agents", audit_logger=audit)

    try:
        config = orch.load_agent_file(agent_yaml)
    except FileNotFoundError as exc:
        console.print(f"[red]Error: {exc}[/red]")
        audit.close()
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"[red]Failed to load agent: {exc}[/red]")
        audit.close()
        raise typer.Exit(1)

    agent = orch.build_agent(config)

    console.print(
        Panel(
            f"[bold]Chatting with:[/bold] {config['name']}\n"
            f"[dim]{config.get('description', '')}[/dim]\n\n"
            f"Tools: {', '.join(t['name'] for t in agent._all_tool_schemas()) or 'none'}\n\n"
            f"[dim]Type your message and press Enter. 'exit' or Ctrl+C to quit.[/dim]",
            title="[cyan]Chat Session[/cyan]",
            border_style="cyan",
        )
    )

    messages: list[dict] = []
    tools = agent._all_tool_schemas()

    try:
        while True:
            try:
                user_input = input("\n[You] > ").strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]Goodbye![/dim]")
                break

            if user_input.lower() in ("exit", "quit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break

            if not user_input:
                continue

            messages.append({"role": "user", "content": user_input})

            turn = 0
            while turn < agent.max_turns:
                turn += 1
                response = agent.provider.create_message(
                    model=agent.model,
                    system=agent.system_prompt,
                    messages=messages,
                    tools=tools,
                    max_tokens=8096,
                )

                messages.append({
                    "role": "assistant",
                    "content": [b.to_dict() for b in response.content],
                })

                if response.stop_reason == "end_turn":
                    text = agent._extract_text(response.content)
                    console.print(f"\n[bold cyan][{agent.name}][/bold cyan] {text}")
                    break

                if response.stop_reason == "tool_use":
                    tool_results = agent._handle_tool_use_blocks(response.content)
                    messages.append({"role": "user", "content": tool_results})
                    continue

                console.print(
                    f"[yellow]Unexpected stop_reason: {response.stop_reason}[/yellow]"
                )
                break
    finally:
        agent.mcp_manager.shutdown()
        audit.close()


@app.command()
def list_tools(
    agent_yaml: str = typer.Argument(..., help="Path to agent YAML file"),
):
    """List all tools available to an agent (no session needed)."""
    from framework.orchestrator import Orchestrator

    orch = Orchestrator(agents_dir="agents", audit_logger=None)
    try:
        config = orch.load_agent_file(agent_yaml)
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1)

    agent = orch.build_agent(config)
    schemas = agent._all_tool_schemas()

    console.print(f"\n[bold]Tools for agent '{config['name']}':[/bold]\n")
    for schema in schemas:
        props = schema.get("input_schema", {}).get("properties", {})
        prop_str = ", ".join(props.keys()) if props else "(no args)"
        console.print(f"  [yellow]{schema['name']}[/yellow]({prop_str})")
        if schema.get("description"):
            console.print(f"    [dim]{schema['description']}[/dim]")

    agent.mcp_manager.shutdown()


if __name__ == "__main__":
    app()
