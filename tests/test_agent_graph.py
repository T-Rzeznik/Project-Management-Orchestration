"""Tests for the Python agent definition (LangGraph)."""

from unittest.mock import patch, MagicMock

import pytest

from agents.project_creator import AGENT_NAME, MODEL_NAME, SYSTEM_PROMPT, build_agent


class TestAgentConfig:
    def test_agent_name(self):
        assert AGENT_NAME == "project_creator"

    def test_model_name(self):
        assert MODEL_NAME == "gemini-2.5-flash-lite"

    def test_system_prompt_contains_instructions(self):
        assert "project management" in SYSTEM_PROMPT.lower()
        assert "read_github_repo" in SYSTEM_PROMPT
        assert "create_project" in SYSTEM_PROMPT


class TestBuildAgent:
    def test_returns_runnable(self):
        """build_agent should return a LangGraph CompiledGraph (a Runnable)."""
        from langchain_core.tools import tool

        @tool
        def dummy_tool(x: str) -> str:
            """A dummy tool."""
            return x

        with patch("agents.project_creator.ChatGoogleGenerativeAI") as mock_llm_cls:
            mock_llm_cls.return_value = MagicMock()
            agent = build_agent(tools=[dummy_tool])

        # LangGraph's create_react_agent returns a CompiledGraph which is a Runnable
        assert hasattr(agent, "invoke")

    def test_passes_callbacks_to_llm(self):
        from langchain_core.tools import tool

        @tool
        def dummy_tool(x: str) -> str:
            """A dummy tool."""
            return x

        mock_callback = MagicMock()

        with patch("agents.project_creator.ChatGoogleGenerativeAI") as mock_llm_cls:
            mock_llm_cls.return_value = MagicMock()
            build_agent(tools=[dummy_tool], callbacks=[mock_callback])

        # Verify callbacks were passed to the LLM constructor
        call_kwargs = mock_llm_cls.call_args
        assert mock_callback in call_kwargs.kwargs.get("callbacks", [])

    def test_uses_correct_model(self):
        from langchain_core.tools import tool

        @tool
        def dummy_tool(x: str) -> str:
            """A dummy tool."""
            return x

        with patch("agents.project_creator.ChatGoogleGenerativeAI") as mock_llm_cls:
            mock_llm_cls.return_value = MagicMock()
            build_agent(tools=[dummy_tool])

        call_kwargs = mock_llm_cls.call_args
        assert call_kwargs.kwargs.get("model") == "gemini-2.5-flash-lite"
