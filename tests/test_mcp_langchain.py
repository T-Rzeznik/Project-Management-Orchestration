"""Tests for MCP-to-LangChain adapter."""

from unittest.mock import MagicMock

import pytest

from tools.mcp_langchain import mcp_tools_as_langchain


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
