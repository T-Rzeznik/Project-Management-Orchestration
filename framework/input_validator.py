"""Input validation — SI-10 (input validation), SI-3 (malicious code) (NIST 800-53 Rev5).

All validation functions raise ValueError with a control-tagged message on failure.
The tag (e.g. "SI-3:", "SI-10:", "AC-3:") makes control mapping auditable.
"""

from __future__ import annotations

import ipaddress
import re
import socket
import urllib.parse
from typing import Any

import jsonschema

# ---------------------------------------------------------------------------
# SI-10 size limits
# ---------------------------------------------------------------------------
MAX_COMMAND_LEN: int = 4_096        # characters
MAX_CONTENT_BYTES: int = 10 * 1024 * 1024  # 10 MB
MAX_URL_LEN: int = 2_048            # characters
MAX_BASH_TIMEOUT: int = 300         # seconds

# ---------------------------------------------------------------------------
# SC-8 / SI-10: allowed URL schemes
# ---------------------------------------------------------------------------
_ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})

# ---------------------------------------------------------------------------
# AC-3 / SI-10: RFC-1918 and reserved ranges (SSRF prevention)
# ---------------------------------------------------------------------------
_PRIVATE_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),   # link-local / AWS EC2 metadata
    ipaddress.ip_network("100.64.0.0/10"),    # shared address space (RFC 6598)
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

# ---------------------------------------------------------------------------
# SI-3: Bash command blocklist
# These patterns are blocked unconditionally *before* the human verification
# gate. FedRAMP High requires machine-level enforcement, not sole reliance on
# human review.
# ---------------------------------------------------------------------------
_BASH_BLOCKLIST: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+|--force\s+)?/", re.I),
     "rm of root-anchored path"),
    (re.compile(r"\bmkfs\b", re.I),
     "filesystem format"),
    (re.compile(r"\bdd\b.*\bof=/dev/", re.I),
     "raw device write via dd"),
    (re.compile(r">\s*/dev/sd[a-z]\b", re.I),
     "redirect to block device"),
    (re.compile(r"\bshred\b", re.I),
     "secure file deletion"),
    (re.compile(r"\bwipefs\b", re.I),
     "filesystem wipe"),
    (re.compile(r":\(\)\s*\{.*\}.*:"),
     "fork bomb"),
    (re.compile(r"\bcurl\b[^|]*\|\s*(bash|sh|python3?|perl|ruby)\b", re.I),
     "curl pipe-to-shell"),
    (re.compile(r"\bwget\b[^|]*\|\s*(bash|sh|python3?|perl|ruby)\b", re.I),
     "wget pipe-to-shell"),
    (re.compile(r">\s*/etc/(passwd|shadow|sudoers|crontab)\b", re.I),
     "system credential file overwrite"),
    (re.compile(r"\biptables\s+-F\b", re.I),
     "firewall rule flush"),
    (re.compile(r"\bufw\s+disable\b", re.I),
     "firewall disable"),
    (re.compile(r"\bkill\s+-9\s+-1\b", re.I),
     "kill all processes"),
    (re.compile(r"\bchmod\s+(777|a\+rwx)\s+/", re.I),
     "world-write on root-anchored path"),
]


# ---------------------------------------------------------------------------
# Public validators
# ---------------------------------------------------------------------------

def validate_bash_command(command: str) -> str:
    """
    Validate a shell command against SI-3 blocklist and SI-10 size limits.
    Raises ValueError if blocked. Returns command string if it passes.
    """
    if len(command) > MAX_COMMAND_LEN:
        raise ValueError(
            f"SI-10: Command length {len(command)} exceeds maximum {MAX_COMMAND_LEN} characters"
        )
    for pattern, desc in _BASH_BLOCKLIST:
        if pattern.search(command):
            raise ValueError(f"SI-3: Command blocked — matches denylist pattern: '{desc}'")
    return command


def validate_bash_timeout(timeout: int) -> int:
    """Cap bash timeout to MAX_BASH_TIMEOUT (SI-10: prevents indefinite blocking)."""
    return min(max(1, int(timeout)), MAX_BASH_TIMEOUT)


def validate_url(url: str) -> str:
    """
    Validate a URL for safe fetching.

    Blocks: non-http(s) schemes, private/loopback IPs (SSRF), oversized URLs.
    Raises ValueError on failure. Returns validated URL string on success.
    """
    if len(url) > MAX_URL_LEN:
        raise ValueError(
            f"SI-10: URL length {len(url)} exceeds maximum {MAX_URL_LEN} characters"
        )

    try:
        parsed = urllib.parse.urlparse(url)
    except Exception as exc:
        raise ValueError(f"SI-10: Malformed URL: {exc}") from exc

    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise ValueError(
            f"SI-10/SC-8: URL scheme '{scheme}' is not permitted. "
            f"Allowed: {sorted(_ALLOWED_SCHEMES)}"
        )

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("SI-10: URL contains no hostname")

    _check_ssrf(hostname)
    return url


def _check_ssrf(hostname: str) -> None:
    """
    Resolve hostname and reject if it points to a private/reserved address.
    Fail-closed policy: unresolvable hosts are rejected (AC-3).
    """
    try:
        results = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValueError(
            f"AC-3/SI-10: Cannot resolve hostname '{hostname}': {exc}. "
            "Unresolvable hosts are blocked (fail-closed policy)."
        ) from exc

    for (_, _, _, _, sockaddr) in results:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        if ip.is_loopback or ip.is_link_local or ip.is_multicast:
            raise ValueError(
                f"AC-3/SI-10: SSRF blocked — '{hostname}' resolves to "
                f"reserved address {ip_str}"
            )

        for network in _PRIVATE_NETWORKS:
            try:
                if ip in network:
                    raise ValueError(
                        f"AC-3/SI-10: SSRF blocked — '{hostname}' resolves to "
                        f"private/reserved address {ip_str} (range: {network})"
                    )
            except TypeError:
                continue


def check_content_size(
    content: str, field_name: str, max_bytes: int = MAX_CONTENT_BYTES
) -> None:
    """Raise ValueError if content exceeds size limit (SI-10)."""
    size = len(content.encode("utf-8", errors="replace"))
    if size > max_bytes:
        raise ValueError(
            f"SI-10: '{field_name}' size {size:,} bytes exceeds "
            f"maximum {max_bytes:,} bytes ({max_bytes // 1_048_576} MB)"
        )


def validate_tool_args(tool_name: str, args: dict[str, Any], schema: dict) -> None:
    """
    Re-validate tool arguments against their declared input_schema.

    Called after human edits in the verification gate (SI-10): ensures that
    operator-edited args still conform to the tool's declared schema before
    execution.

    Raises jsonschema.ValidationError on failure.
    """
    input_schema = schema.get("input_schema", {})
    try:
        jsonschema.validate(instance=args, schema=input_schema)
    except jsonschema.ValidationError as exc:
        raise jsonschema.ValidationError(
            f"SI-10: Edited args for tool '{tool_name}' failed schema validation: "
            f"{exc.message}"
        ) from exc
