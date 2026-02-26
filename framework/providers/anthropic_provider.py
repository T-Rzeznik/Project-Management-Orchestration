"""Anthropic provider — wraps the standard anthropic Python SDK."""

from __future__ import annotations

import anthropic

from framework.providers.base import (
    BaseProvider,
    NormalizedResponse,
    NormalizedTextBlock,
    NormalizedToolUseBlock,
)


class AnthropicProvider(BaseProvider):
    """Provider using the Anthropic API directly (default)."""

    def __init__(self) -> None:
        self._client = anthropic.Anthropic()

    def create_message(
        self,
        model: str,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int = 8096,
    ) -> NormalizedResponse:
        response = self._client.messages.create(
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

        return NormalizedResponse(stop_reason=response.stop_reason, content=content)
