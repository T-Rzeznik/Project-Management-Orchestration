"""Vertex AI provider — Claude via AnthropicVertex and Gemini via vertexai SDK.

Model routing:
  - model name starts with "claude-"  →  AnthropicVertex (same API as Anthropic SDK)
  - everything else (e.g. "gemini-2.0-flash")  →  Gemini via vertexai GenerativeModel

Authentication:
  Both paths use Application Default Credentials (ADC).
  Run:  gcloud auth application-default login
  Or set GOOGLE_APPLICATION_CREDENTIALS to a service-account key file.

Required packages:
  pip install "anthropic[vertex]" google-cloud-aiplatform
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from framework.providers.base import (
    BaseProvider,
    NormalizedResponse,
    NormalizedTextBlock,
    NormalizedToolUseBlock,
    struct_to_dict,
)

if TYPE_CHECKING:
    pass


class VertexProvider(BaseProvider):
    """Provider backed by Google Cloud Vertex AI.

    Each Agent instance gets its own VertexProvider, so the stateful Gemini
    chat session is safely scoped to a single task run.
    """

    def __init__(self, project: str, location: str = "us-central1") -> None:
        self.project = project
        self.location = location

        self._vertex_initialized = False
        self._claude_client: Any = None

        # Gemini stateful chat — created lazily on first Gemini call
        self._gemini_chat: Any = None
        # Maps normalized tool-call IDs → tool names for routing function responses
        self._tool_id_map: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def create_message(
        self,
        model: str,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int = 8096,
    ) -> NormalizedResponse:
        if model.lower().startswith("claude"):
            return self._create_claude_message(model, system, messages, tools, max_tokens)
        return self._create_gemini_message(model, system, messages, tools, max_tokens)

    # ------------------------------------------------------------------
    # Claude via AnthropicVertex
    # ------------------------------------------------------------------

    def _get_claude_client(self) -> Any:
        if self._claude_client is None:
            from anthropic import AnthropicVertex  # requires anthropic[vertex]

            self._claude_client = AnthropicVertex(
                project_id=self.project,
                region=self.location,
            )
        return self._claude_client

    def _create_claude_message(
        self,
        model: str,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int,
    ) -> NormalizedResponse:
        import anthropic

        client = self._get_claude_client()
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            tools=tools if tools else anthropic.NOT_GIVEN,
            messages=messages,
        )

        content: list[NormalizedTextBlock | NormalizedToolUseBlock] = []
        for block in response.content:
            if block.type == "text":
                content.append(NormalizedTextBlock(text=block.text))
            elif block.type == "tool_use":
                content.append(
                    NormalizedToolUseBlock(
                        id=block.id,
                        name=block.name,
                        input=block.input or {},
                    )
                )
        return NormalizedResponse(
            stop_reason=response.stop_reason,
            content=content,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    # ------------------------------------------------------------------
    # Gemini via vertexai SDK (stateful chat session)
    # ------------------------------------------------------------------

    def _init_vertexai(self) -> None:
        if not self._vertex_initialized:
            import vertexai  # google-cloud-aiplatform

            vertexai.init(project=self.project, location=self.location)
            self._vertex_initialized = True

    def _create_gemini_message(
        self,
        model: str,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int,
    ) -> NormalizedResponse:
        self._init_vertexai()
        from vertexai.generative_models import GenerativeModel  # type: ignore[import]

        gemini_tools = self._build_gemini_tools(tools)

        # Lazily create a chat session (scoped to this Agent/task lifetime)
        if self._gemini_chat is None:
            gemini_model = GenerativeModel(
                model_name=model,
                system_instruction=system or None,
            )
            self._gemini_chat = gemini_model.start_chat()

        send_content = self._build_send_content(messages[-1])
        generation_config = {"max_output_tokens": max_tokens}

        response = self._gemini_chat.send_message(
            content=send_content,
            generation_config=generation_config,
            tools=gemini_tools if gemini_tools else None,
        )
        return self._normalize_gemini_response(response)

    # ------------------------------------------------------------------
    # Gemini helpers
    # ------------------------------------------------------------------

    def _build_gemini_tools(self, tools: list[dict]) -> Any | None:
        """Convert Anthropic-format tool schemas to Gemini Tool objects."""
        if not tools:
            return None
        from vertexai.generative_models import FunctionDeclaration, Tool  # type: ignore[import]

        declarations = [
            FunctionDeclaration(
                name=t["name"],
                description=t.get("description", ""),
                parameters=self._clean_schema(t.get("input_schema", {})),
            )
            for t in tools
        ]
        return [Tool(function_declarations=declarations)]

    def _build_send_content(self, message: dict) -> Any:
        """Build the content argument for chat.send_message() from a message dict."""
        from vertexai.generative_models import Part  # type: ignore[import]

        raw = message.get("content", "")
        if isinstance(raw, str):
            return raw

        parts: list[Any] = []
        for block in raw:
            btype = (
                block.get("type") if isinstance(block, dict)
                else getattr(block, "type", None)
            )

            if btype == "text":
                text = block["text"] if isinstance(block, dict) else block.text
                if text:
                    parts.append(Part.from_text(text))

            elif btype == "tool_result":
                tool_use_id = (
                    block["tool_use_id"] if isinstance(block, dict)
                    else block.tool_use_id
                )
                result_content = (
                    block.get("content", "")
                    if isinstance(block, dict)
                    else getattr(block, "content", "")
                )
                tool_name = self._tool_id_map.get(tool_use_id, tool_use_id)
                parts.append(
                    Part.from_function_response(
                        name=tool_name,
                        response={"content": str(result_content)},
                    )
                )

        return parts if parts else ""

    def _normalize_gemini_response(self, response: Any) -> NormalizedResponse:
        """Convert a Gemini GenerateContentResponse to NormalizedResponse."""
        content: list[NormalizedTextBlock | NormalizedToolUseBlock] = []
        has_tool_calls = False

        candidates = getattr(response, "candidates", [])
        if not candidates:
            return NormalizedResponse(stop_reason="end_turn", content=[])

        for part in candidates[0].content.parts:
            text = getattr(part, "text", None)
            if text:
                content.append(NormalizedTextBlock(text=text))
                continue

            fc = getattr(part, "function_call", None)
            if fc and getattr(fc, "name", None):
                tool_id = f"call_{uuid.uuid4().hex[:12]}"
                tool_name = fc.name
                raw_args = getattr(fc, "args", {})
                tool_input = struct_to_dict(raw_args) if raw_args else {}

                self._tool_id_map[tool_id] = tool_name
                content.append(
                    NormalizedToolUseBlock(
                        id=tool_id,
                        name=tool_name,
                        input=tool_input,
                    )
                )
                has_tool_calls = True

        usage = getattr(response, "usage_metadata", None)
        input_tokens = getattr(usage, "prompt_token_count", 0) or 0
        output_tokens = getattr(usage, "candidates_token_count", 0) or 0

        return NormalizedResponse(
            stop_reason="tool_use" if has_tool_calls else "end_turn",
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    @staticmethod
    def _clean_schema(schema: dict) -> dict:
        """Strip JSON Schema fields unsupported by Gemini FunctionDeclaration."""
        _UNSUPPORTED = {"$schema", "additionalProperties", "$defs", "definitions", "default"}
        if not isinstance(schema, dict):
            return schema
        cleaned = {k: v for k, v in schema.items() if k not in _UNSUPPORTED}
        if "properties" in cleaned:
            cleaned["properties"] = {
                k: VertexProvider._clean_schema(v)
                for k, v in cleaned["properties"].items()
            }
        if "items" in cleaned:
            cleaned["items"] = VertexProvider._clean_schema(cleaned["items"])
        return cleaned
