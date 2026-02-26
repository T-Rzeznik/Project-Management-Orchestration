"""Provider abstraction — normalized types shared across all AI backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NormalizedTextBlock:
    type: str = "text"
    text: str = ""

    def to_dict(self) -> dict:
        return {"type": "text", "text": self.text}


@dataclass
class NormalizedToolUseBlock:
    type: str = "tool_use"
    id: str = ""
    name: str = ""
    input: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "type": "tool_use",
            "id": self.id,
            "name": self.name,
            "input": self.input,
        }


@dataclass
class NormalizedResponse:
    stop_reason: str  # "end_turn" | "tool_use"
    content: list[NormalizedTextBlock | NormalizedToolUseBlock]


class BaseProvider(ABC):
    """Abstract base for AI model providers.

    Implementations must convert provider-specific formats to/from the
    canonical Anthropic message format used throughout the agent loop.
    """

    @abstractmethod
    def create_message(
        self,
        model: str,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int = 8096,
    ) -> NormalizedResponse:
        """Send a conversation turn and return a normalized response."""
        ...


def struct_to_dict(value: Any) -> Any:
    """Recursively convert proto Struct-like objects to plain Python types."""
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    try:
        items = dict(value)
        return {k: struct_to_dict(v) for k, v in items.items()}
    except (TypeError, AttributeError):
        pass
    try:
        return [struct_to_dict(item) for item in value]
    except TypeError:
        return value
