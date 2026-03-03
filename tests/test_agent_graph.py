"""Tests for the Python agent definition (LangGraph)."""

from unittest.mock import patch, MagicMock

import pytest

from agents.project_creator import AGENT_NAME, MODEL_NAME, SYSTEM_PROMPT, build_agent


class TestAgentConfig:
    def test_agent_name(self):
        assert AGENT_NAME == "project_creator"

    def test_model_name(self):
        assert MODEL_NAME == "gemini-2.5-flash"

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
        assert call_kwargs.kwargs.get("model") == "gemini-2.5-flash"


class TestBuildAgentInterruptSupport:
    """Tests for checkpointer and interrupt_before params in build_agent."""

    def test_build_agent_without_checkpointer_defaults_to_none(self):
        """build_agent() with no checkpointer should not pass it to create_react_agent."""
        from langchain_core.tools import tool

        @tool
        def dummy_tool(x: str) -> str:
            """A dummy tool."""
            return x

        with patch("agents.project_creator.ChatGoogleGenerativeAI") as MockLLM:
            MockLLM.return_value = MagicMock()
            with patch("agents.project_creator.create_react_agent") as mock_create:
                mock_create.return_value = MagicMock()
                build_agent(tools=[dummy_tool])
                call_kwargs = mock_create.call_args.kwargs
                assert call_kwargs.get("checkpointer") is None
                assert call_kwargs.get("interrupt_before") is None

    def test_build_agent_with_checkpointer(self):
        """build_agent() should forward checkpointer to create_react_agent."""
        from langchain_core.tools import tool

        @tool
        def dummy_tool(x: str) -> str:
            """A dummy tool."""
            return x

        mock_checkpointer = MagicMock()

        with patch("agents.project_creator.ChatGoogleGenerativeAI") as MockLLM:
            MockLLM.return_value = MagicMock()
            with patch("agents.project_creator.create_react_agent") as mock_create:
                mock_create.return_value = MagicMock()
                build_agent(tools=[dummy_tool], checkpointer=mock_checkpointer)
                call_kwargs = mock_create.call_args.kwargs
                assert call_kwargs["checkpointer"] is mock_checkpointer

    def test_build_agent_with_interrupt_before(self):
        """build_agent() should forward interrupt_before to create_react_agent."""
        from langchain_core.tools import tool

        @tool
        def dummy_tool(x: str) -> str:
            """A dummy tool."""
            return x

        with patch("agents.project_creator.ChatGoogleGenerativeAI") as MockLLM:
            MockLLM.return_value = MagicMock()
            with patch("agents.project_creator.create_react_agent") as mock_create:
                mock_create.return_value = MagicMock()
                build_agent(tools=[dummy_tool], interrupt_before=["tools"])
                call_kwargs = mock_create.call_args.kwargs
                assert call_kwargs["interrupt_before"] == ["tools"]
