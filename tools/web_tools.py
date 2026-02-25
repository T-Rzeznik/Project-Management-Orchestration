"""Built-in web fetch tool — SI-10/SC-8/AC-3 (NIST 800-53 Rev5).

Controls applied before any network request:
  SI-10: URL length, scheme, and content-size validation
  SC-8:  only http/https schemes permitted
  AC-3:  SSRF prevention — RFC-1918 / loopback addresses are blocked
  SC-28: URL scrubbing in audit log (caller responsibility; raw URL returned to agent)

Redirects are NOT automatically followed (follow_redirects=False) to prevent
an open-redirect from bypassing SSRF checks on the final destination.
"""

from __future__ import annotations

import httpx

from framework.input_validator import check_content_size, validate_url


def make_web_function() -> dict:
    """Return the web_fetch callable."""

    def web_fetch(url: str, timeout: int = 30) -> str:
        """
        Fetch the content of a URL and return the response body as text.

        SI-10: URL is validated (scheme, length, SSRF) before any network I/O.
        SC-8:  only http/https allowed.
        AC-3:  private/loopback destinations blocked.
        """
        # SI-10 / SC-8 / AC-3: validate before making any network call
        validate_url(url)

        # SI-10: cap timeout
        safe_timeout = min(int(timeout), 60)

        try:
            with httpx.Client(
                follow_redirects=False,  # AC-3: don't auto-follow to unvalidated targets
                timeout=safe_timeout,
                headers={"User-Agent": "OrchestrationFramework/1.0"},
            ) as client:
                response = client.get(url)
                response.raise_for_status()

                text = response.text
                # SI-10: cap response size
                check_content_size(text, "response_body")

                content_type = response.headers.get("content-type", "")
                return (
                    f"[Status: {response.status_code}] "
                    f"[Content-Type: {content_type}]\n\n{text}"
                )
        except httpx.HTTPStatusError as exc:
            return f"HTTP error {exc.response.status_code}: {exc}"
        except httpx.RequestError as exc:
            return f"Request error: {exc}"
        except ValueError as exc:
            # Re-raise validation errors so ToolRegistry can log them as TOOL_BLOCKED
            raise
        except Exception as exc:
            return f"Error fetching URL: {exc}"

    return {"web_fetch": web_fetch}


WEB_TOOL_SCHEMA: dict = {
    "name": "web_fetch",
    "description": (
        "Fetch the content of a web URL and return the response body. "
        "Only http/https allowed. Private/internal addresses are blocked."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch (http/https only)"},
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (max 60, default 30)",
                "default": 30,
            },
        },
        "required": ["url"],
    },
}
