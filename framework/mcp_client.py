"""MCP client manager — AU-2/SC-28/SI-10 (NIST 800-53 Rev5).

Security notes:
  SC-28: MCP server `env` blocks (which may contain credentials) are passed to
         the subprocess but NEVER written to audit logs.
  SI-10: MCP tool responses are size-capped before being returned to the agent.
  AU-2:  MCP_CONNECT and MCP_CONNECT_FAILED events are emitted per server.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from rich.console import Console

from framework.audit_logger import AuditEventType
from framework.input_validator import MAX_CONTENT_BYTES

if TYPE_CHECKING:
    from framework.audit_logger import AuditLogger

console = Console()

# SI-10: max bytes to return from any single MCP tool call
_MCP_RESULT_MAX_BYTES = MAX_CONTENT_BYTES


def _to_anthropic_schema(mcp_tool) -> dict:
    """Convert an MCP tool definition to Anthropic API tool schema."""
    return {
        "name": mcp_tool.name,
        "description": mcp_tool.description or "",
        "input_schema": mcp_tool.inputSchema or {"type": "object", "properties": {}},
    }


class MCPConnection:
    """Represents a live connection to a single MCP server."""

    def __init__(self, name: str, session: ClientSession, tools: list[dict]):
        self.name = name
        self.session = session
        self.tools = tools  # Anthropic-formatted schemas

    @property
    def tool_names(self) -> list[str]:
        return [t["name"] for t in self.tools]


class MCPClientManager:
    """Manages MCP server connections for an agent."""

    def __init__(self):
        self._connections: dict[str, MCPConnection] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._contexts: list = []

    # ------------------------------------------------------------------
    # Public sync interface
    # ------------------------------------------------------------------

    def connect_all(
        self,
        server_configs: list[dict],
        audit_logger: "AuditLogger | None" = None,
    ) -> None:
        """Connect to all configured MCP servers synchronously."""
        if not server_configs:
            return
        loop = self._get_loop()
        loop.run_until_complete(self._connect_all_async(server_configs, audit_logger))

    def list_tools(self, server_name: str) -> list[dict]:
        conn = self._connections.get(server_name)
        return conn.tools if conn else []

    def all_tools(self) -> list[dict]:
        schemas = []
        for conn in self._connections.values():
            schemas.extend(conn.tools)
        return schemas

    def call_tool(self, tool_name: str, args: dict[str, Any]) -> str:
        server_name = self._find_server_for_tool(tool_name)
        if not server_name:
            return f"Error: MCP tool '{tool_name}' not found in any connected server"
        loop = self._get_loop()
        return loop.run_until_complete(self._call_tool_async(server_name, tool_name, args))

    def shutdown(self) -> None:
        loop = self._get_loop()
        loop.run_until_complete(self._shutdown_async())

    # ------------------------------------------------------------------
    # Async internals
    # ------------------------------------------------------------------

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop

    async def _connect_all_async(
        self, server_configs: list[dict], audit_logger: "AuditLogger | None"
    ) -> None:
        for config in server_configs:
            transport = config.get("transport", "stdio")
            name = config["name"]
            try:
                if transport == "stdio":
                    tool_count = await self._connect_stdio(name, config)
                    # AU-12: MCP_CONNECT — SC-28: env values not logged
                    if audit_logger:
                        audit_logger.log(
                            AuditEventType.MCP_CONNECT,
                            server_name=name,
                            transport=transport,
                            command=config.get("command"),
                            tool_count=tool_count,
                            # env deliberately omitted (SC-28)
                        )
                else:
                    console.print(
                        f"[yellow]Warning: transport '{transport}' not supported "
                        f"for MCP server '{name}'. Skipping.[/yellow]"
                    )
            except Exception as exc:
                console.print(
                    f"[red]Failed to connect to MCP server '{name}': {exc}[/red]"
                )
                if audit_logger:
                    audit_logger.log(
                        AuditEventType.MCP_CONNECT_FAILED,
                        server_name=name,
                        detail=str(exc),
                    )

    async def _connect_stdio(self, name: str, config: dict) -> int:
        """Connect to a stdio MCP server. Returns number of discovered tools."""
        command = config["command"]
        args = config.get("args", [])
        # SC-28: env may contain credentials — passed to subprocess but not logged
        env = config.get("env", None)

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=env,
        )

        read_stream, write_stream = await self._enter_stdio_context(server_params)
        session = ClientSession(read_stream, write_stream)
        await session.__aenter__()
        await session.initialize()

        result = await session.list_tools()
        tools = [_to_anthropic_schema(t) for t in result.tools]

        self._connections[name] = MCPConnection(name=name, session=session, tools=tools)
        console.print(
            f"[green]Connected to MCP server '{name}' — {len(tools)} tools available.[/green]"
        )
        return len(tools)

    async def _enter_stdio_context(self, server_params: StdioServerParameters):
        ctx = stdio_client(server_params)
        streams = await ctx.__aenter__()
        self._contexts.append(ctx)
        return streams

    async def _call_tool_async(
        self, server_name: str, tool_name: str, args: dict[str, Any]
    ) -> str:
        conn = self._connections[server_name]
        try:
            result = await conn.session.call_tool(tool_name, args)
            parts = []
            for block in result.content:
                parts.append(block.text if hasattr(block, "text") else str(block))
            text = "\n".join(parts)

            # SI-10: cap MCP response size
            encoded = text.encode("utf-8", errors="replace")
            if len(encoded) > _MCP_RESULT_MAX_BYTES:
                text = (
                    encoded[:_MCP_RESULT_MAX_BYTES].decode("utf-8", errors="replace")
                    + f"\n...[truncated: response exceeded {_MCP_RESULT_MAX_BYTES // 1_048_576} MB]"
                )
            return text
        except Exception as exc:
            return f"MCP tool error: {exc}"

    async def _shutdown_async(self) -> None:
        for conn in self._connections.values():
            try:
                await conn.session.__aexit__(None, None, None)
            except Exception:
                pass
        for ctx in self._contexts:
            try:
                await ctx.__aexit__(None, None, None)
            except Exception:
                pass
        self._connections.clear()
        self._contexts.clear()

    def _find_server_for_tool(self, tool_name: str) -> str | None:
        for name, conn in self._connections.items():
            if tool_name in conn.tool_names:
                return name
        return None
