"""Tests for MCP-to-LangChain adapter."""

from unittest.mock import MagicMock

import pytest

from tools.mcp_langchain import mcp_tools_as_langchain, json_schema_to_pydantic_model


class TestMcpToolsAsLangchain:
    def test_converts_single_tool(self):
        mock_mgr = MagicMock()
        mock_mgr.all_tools.return_value = [{
            "name": "get_file_contents",
            "description": "Read a file from a repo",
            "input_schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repo owner"},
                    "repo": {"type": "string", "description": "Repo name"},
                    "path": {"type": "string", "description": "File path"},
                },
                "required": ["owner", "repo", "path"],
            },
        }]

        tools = mcp_tools_as_langchain(mock_mgr)
        assert len(tools) == 1
        assert tools[0].name == "get_file_contents"
        assert tools[0].description == "Read a file from a repo"

    def test_converts_multiple_tools(self):
        mock_mgr = MagicMock()
        mock_mgr.all_tools.return_value = [
            {
                "name": "tool_a",
                "description": "Tool A",
                "input_schema": {"type": "object", "properties": {}},
            },
            {
                "name": "tool_b",
                "description": "Tool B",
                "input_schema": {"type": "object", "properties": {}},
            },
        ]

        tools = mcp_tools_as_langchain(mock_mgr)
        assert len(tools) == 2
        names = {t.name for t in tools}
        assert names == {"tool_a", "tool_b"}

    def test_empty_tools_returns_empty_list(self):
        mock_mgr = MagicMock()
        mock_mgr.all_tools.return_value = []

        tools = mcp_tools_as_langchain(mock_mgr)
        assert tools == []

    def test_tool_invocation_dispatches_to_mcp(self):
        mock_mgr = MagicMock()
        mock_mgr.all_tools.return_value = [{
            "name": "get_file_contents",
            "description": "Read a file",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                },
                "required": ["path"],
            },
        }]
        mock_mgr.call_tool.return_value = "file content here"

        tools = mcp_tools_as_langchain(mock_mgr)
        result = tools[0].invoke({"path": "README.md"})

        mock_mgr.call_tool.assert_called_once_with("get_file_contents", {"path": "README.md"})
        assert result == "file content here"

    def test_returns_structured_tools(self):
        from langchain_core.tools import BaseTool

        mock_mgr = MagicMock()
        mock_mgr.all_tools.return_value = [{
            "name": "test_tool",
            "description": "A test",
            "input_schema": {"type": "object", "properties": {}},
        }]

        tools = mcp_tools_as_langchain(mock_mgr)
        assert isinstance(tools[0], BaseTool)

    def test_none_manager_returns_empty(self):
        tools = mcp_tools_as_langchain(None)
        assert tools == []


class TestJsonSchemaToModel:
    """Tests for json_schema_to_pydantic_model — converts JSON Schema to Pydantic."""

    def test_string_field(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        Model = json_schema_to_pydantic_model("TestTool", schema)
        instance = Model(name="hello")
        assert instance.name == "hello"

    def test_integer_field(self):
        schema = {
            "type": "object",
            "properties": {"count": {"type": "integer"}},
            "required": ["count"],
        }
        Model = json_schema_to_pydantic_model("TestTool", schema)
        instance = Model(count=42)
        assert instance.count == 42

    def test_number_field(self):
        schema = {
            "type": "object",
            "properties": {"price": {"type": "number"}},
            "required": ["price"],
        }
        Model = json_schema_to_pydantic_model("TestTool", schema)
        instance = Model(price=9.99)
        assert instance.price == 9.99

    def test_boolean_field(self):
        schema = {
            "type": "object",
            "properties": {"active": {"type": "boolean"}},
            "required": ["active"],
        }
        Model = json_schema_to_pydantic_model("TestTool", schema)
        instance = Model(active=True)
        assert instance.active is True

    def test_array_field(self):
        schema = {
            "type": "object",
            "properties": {"tags": {"type": "array"}},
            "required": ["tags"],
        }
        Model = json_schema_to_pydantic_model("TestTool", schema)
        instance = Model(tags=["a", "b"])
        assert instance.tags == ["a", "b"]

    def test_object_field(self):
        schema = {
            "type": "object",
            "properties": {"metadata": {"type": "object"}},
            "required": ["metadata"],
        }
        Model = json_schema_to_pydantic_model("TestTool", schema)
        instance = Model(metadata={"key": "val"})
        assert instance.metadata == {"key": "val"}

    def test_optional_field_has_default_none(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "label": {"type": "string"},
            },
            "required": ["name"],
        }
        Model = json_schema_to_pydantic_model("TestTool", schema)
        instance = Model(name="hello")
        assert instance.label is None

    def test_field_description_preserved(self):
        schema = {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repository owner"},
            },
            "required": ["owner"],
        }
        Model = json_schema_to_pydantic_model("TestTool", schema)
        field_info = Model.model_fields["owner"]
        assert field_info.description == "Repository owner"

    def test_multiple_required_fields(self):
        schema = {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "path": {"type": "string"},
            },
            "required": ["owner", "repo", "path"],
        }
        Model = json_schema_to_pydantic_model("TestTool", schema)
        instance = Model(owner="pallets", repo="flask", path="README.md")
        assert instance.owner == "pallets"
        assert instance.repo == "flask"
        assert instance.path == "README.md"

    def test_empty_properties(self):
        schema = {"type": "object", "properties": {}}
        Model = json_schema_to_pydantic_model("TestTool", schema)
        instance = Model()
        assert instance is not None

    def test_unknown_type_defaults_to_any(self):
        schema = {
            "type": "object",
            "properties": {"data": {"type": "unknown_type"}},
            "required": ["data"],
        }
        Model = json_schema_to_pydantic_model("TestTool", schema)
        instance = Model(data="anything")
        assert instance.data == "anything"

    def test_missing_type_defaults_to_any(self):
        schema = {
            "type": "object",
            "properties": {"data": {"description": "No type given"}},
            "required": ["data"],
        }
        Model = json_schema_to_pydantic_model("TestTool", schema)
        instance = Model(data=123)
        assert instance.data == 123


class TestArgsSchemaGeneration:
    """Tests that converted MCP tools get a proper args_schema (not None)."""

    def test_tool_has_args_schema(self):
        mock_mgr = MagicMock()
        mock_mgr.all_tools.return_value = [{
            "name": "get_file_contents",
            "description": "Read a file",
            "input_schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repo owner"},
                    "repo": {"type": "string", "description": "Repo name"},
                    "path": {"type": "string", "description": "File path"},
                },
                "required": ["owner", "repo", "path"],
            },
        }]

        tools = mcp_tools_as_langchain(mock_mgr)
        assert tools[0].args_schema is not None

    def test_args_schema_has_correct_fields(self):
        mock_mgr = MagicMock()
        mock_mgr.all_tools.return_value = [{
            "name": "get_file_contents",
            "description": "Read a file",
            "input_schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "path": {"type": "string"},
                },
                "required": ["owner", "repo", "path"],
            },
        }]

        tools = mcp_tools_as_langchain(mock_mgr)
        schema = tools[0].args_schema
        field_names = set(schema.model_fields.keys())
        assert field_names == {"owner", "repo", "path"}

    def test_args_schema_validates_input(self):
        """The generated schema should allow valid input."""
        mock_mgr = MagicMock()
        mock_mgr.all_tools.return_value = [{
            "name": "test_tool",
            "description": "A test tool",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "count": {"type": "integer"},
                },
                "required": ["name"],
            },
        }]

        tools = mcp_tools_as_langchain(mock_mgr)
        schema = tools[0].args_schema
        instance = schema(name="hello", count=5)
        assert instance.name == "hello"
        assert instance.count == 5
