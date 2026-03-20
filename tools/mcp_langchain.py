"""MCP-to-LangChain adapter — converts MCP tools to LangChain StructuredTools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, Field, create_model
from langchain_core.tools import StructuredTool

if TYPE_CHECKING:
    from framework.mcp_client import MCPClientManager

_JSON_TYPE_MAP: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def json_schema_to_pydantic_model(name: str, schema: dict) -> type[BaseModel]:
    """Convert a JSON Schema object to a Pydantic model class.

    Maps JSON Schema types to Python types and handles required/optional fields.
    """
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    field_definitions: dict[str, Any] = {}

    for field_name, field_schema in properties.items():
        json_type = field_schema.get("type", "")
        python_type = _JSON_TYPE_MAP.get(json_type, Any)
        description = field_schema.get("description")

        if field_name in required:
            field_definitions[field_name] = (
                python_type,
                Field(description=description),
            )
        else:
            field_definitions[field_name] = (
                Optional[python_type],
                Field(default=None, description=description),
            )

    return create_model(name, **field_definitions)


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

        args_model = json_schema_to_pydantic_model(name, input_schema)

        # Build a closure that captures the tool name
        def _make_fn(tool_name: str):
            def _invoke(**kwargs: Any) -> str:
                return mcp_manager.call_tool(tool_name, kwargs)
            return _invoke

        tool = StructuredTool.from_function(
            func=_make_fn(name),
            name=name,
            description=description,
            args_schema=args_model,
        )

        tools.append(tool)

    return tools
