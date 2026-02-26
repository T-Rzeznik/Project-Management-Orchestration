"""Provider factory — create the right BaseProvider from agent config."""

from __future__ import annotations

from framework.providers.base import BaseProvider


def create_provider(config: dict) -> BaseProvider:
    """Instantiate a provider from an agent config dict.

    Config example (YAML):
        provider:
          type: vertex_ai
          project: my-gcp-project
          location: us-central1   # optional, default us-central1

    Omitting the ``provider`` block (or setting type to "anthropic") uses the
    standard Anthropic API.
    """
    provider_cfg = config.get("provider", {})
    provider_type = provider_cfg.get("type", "anthropic")

    if provider_type == "anthropic":
        from framework.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider()

    if provider_type == "vertex_ai":
        from framework.providers.vertex_provider import VertexProvider

        project = provider_cfg.get("project")
        if not project:
            raise ValueError(
                "provider.project is required when using the vertex_ai provider. "
                "Add it to your agent YAML:\n"
                "  provider:\n"
                "    type: vertex_ai\n"
                "    project: my-gcp-project"
            )
        location = provider_cfg.get("location", "us-central1")
        return VertexProvider(project=project, location=location)

    raise ValueError(
        f"Unknown provider type: '{provider_type}'. "
        "Valid values: 'anthropic', 'vertex_ai'"
    )
