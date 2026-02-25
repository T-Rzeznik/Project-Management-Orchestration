"""Secret scrubbing for audit logs — SC-28, AU-3 (NIST 800-53 Rev5).

Prevents secrets from being written to audit logs or displayed unnecessarily.
Every value that matches a known secret pattern is replaced with
[REDACTED:<pattern_name>] so the redaction is itself auditable.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any

# Named patterns: pattern_name → compiled regex
# Each pattern is designed to match common secret formats while minimizing false positives.
_PATTERNS: dict[str, re.Pattern] = {
    "anthropic_api_key": re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}", re.IGNORECASE),
    "openai_api_key": re.compile(r"\bsk-[A-Za-z0-9]{20,}"),
    "aws_access_key_id": re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    "github_token": re.compile(r"\bgh[ps]_[A-Za-z0-9]{36}\b", re.IGNORECASE),
    "bearer_token": re.compile(r"\bBearer\s+[A-Za-z0-9\-._~+/]{8,}=*", re.IGNORECASE),
    "pem_private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "generic_password_assign": re.compile(r"\bpassword\s*[=:]\s*\S{4,}", re.IGNORECASE),
    "generic_token_assign": re.compile(r"\btoken\s*[=:]\s*[^\s,}\"']{8,}", re.IGNORECASE),
    "generic_secret_assign": re.compile(r"\bsecret\s*[=:]\s*[^\s,}\"']{8,}", re.IGNORECASE),
}

# Dict keys whose values are always redacted regardless of value content
_SENSITIVE_KEY_NAMES: re.Pattern = re.compile(
    r"(password|secret|token|api[_\-]?key|auth(?:orization)?|credential|"
    r"private[_\-]?key|access[_\-]?key|client[_\-]?secret)",
    re.IGNORECASE,
)

# URL query parameter names to redact
_SENSITIVE_QUERY_PARAMS: frozenset[str] = frozenset({
    "token", "api_key", "apikey", "secret", "password", "auth",
    "access_token", "refresh_token", "key", "private_key", "client_secret",
    "authorization",
})


def scrub_string(s: str) -> str:
    """Replace known secret patterns in a string with [REDACTED:<name>]."""
    if not isinstance(s, str):
        return s
    # Truncate before scanning to bound CPU cost
    if len(s) > 100_000:
        s = s[:100_000] + f"...[truncated {len(s)} chars]"
    for name, pattern in _PATTERNS.items():
        s = pattern.sub(f"[REDACTED:{name}]", s)
    return s


def scrub_dict(data: Any, depth: int = 0) -> Any:
    """
    Recursively scrub secrets from a dict/list/string.
    Returns a new object — never mutates input.
    Caps recursion at depth 10 to handle pathological input (SI-10).
    """
    if depth > 10:
        return "[truncated:max_depth]"

    if isinstance(data, dict):
        result: dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(k, str) and _SENSITIVE_KEY_NAMES.search(k):
                result[k] = "[REDACTED:sensitive_key]"
            else:
                result[k] = scrub_dict(v, depth + 1)
        return result

    if isinstance(data, list):
        return [scrub_dict(item, depth + 1) for item in data]

    if isinstance(data, str):
        return scrub_string(data)

    return data


def scrub_url(url: str) -> str:
    """Redact sensitive query parameters from a URL string."""
    try:
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        redacted = {
            k: (["[REDACTED:query_param]"] if k.lower() in _SENSITIVE_QUERY_PARAMS else v)
            for k, v in params.items()
        }
        new_query = urllib.parse.urlencode(redacted, doseq=True)
        return parsed._replace(query=new_query).geturl()
    except Exception:
        return "[REDACTED:url_parse_error]"
