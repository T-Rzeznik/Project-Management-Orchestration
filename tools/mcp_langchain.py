"""MCP-to-LangChain adapter — converts MCP tools to LangChain StructuredTools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_core.tools import StructuredTool

if TYPE_CHECKING:
    from framework.mcp_client import MCPClientManager


def mcp_tools_as_langchain(mcp_manager: MCPClientManager | None) -> list[StructuredTool]:
    """Convert all MCP tools from a manager into LangChain StructuredTools.

    Each tool dispatches calls back through ``mcp_manager.call_tool()``.
    Returns an empty list if ``mcp_manager`` is None or has no tools.
    """
    if mcp_manager is None:
        return []

    schemas = mcp_manager.all_tools()
    tools: list[StructuredTool] = []

    for schema in schemas:
        name = schema["name"]
        description = schema.get("description", "")
        input_schema = schema.get("input_schema", {"type": "object", "properties": {}})

        # Build a closure that captures the tool name
        def _make_fn(tool_name: str):
            def _invoke(**kwargs: Any) -> str:
                return mcp_manager.call_tool(tool_name, kwargs)
            return _invoke

        tool = StructuredTool.from_function(
            func=_make_fn(name),
            name=name,
            description=description,
            args_schema=None,
        )
        # Override the JSON schema for the tool
        tool.args_schema = None
        # Store the raw schema for serialization
        tool.metadata = {"input_schema": input_schema}

        tools.append(tool)

    return tools
