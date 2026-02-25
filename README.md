# YAML-Based AI Agent Orchestration Framework

A Python framework for defining AI agents in YAML files and running them with
full tool access, MCP server integration, and a human-in-the-loop
**verify-then-commit gate** before every tool call. Built to meet the
**FedRAMP High** baseline (NIST 800-53 Rev5).

---

## Table of Contents

1. [Project Status](#1-project-status)
2. [Architecture](#2-architecture)
3. [File Structure](#3-file-structure)
4. [Installation](#4-installation)
5. [CLI Usage](#5-cli-usage)
6. [YAML Agent Schema](#6-yaml-agent-schema)
7. [Verify-Then-Commit Gate](#7-verify-then-commit-gate)
8. [Built-in Tools](#8-built-in-tools)
9. [MCP Server Integration](#9-mcp-server-integration)
10. [Multi-Agent Handoff](#10-multi-agent-handoff)
11. [Environment Variables](#11-environment-variables)
12. [FedRAMP High Controls](#12-fedramp-high-controls)

---

## 1. Project Status

The framework is fully implemented and syntax-verified. All core components are
wired together and the FedRAMP High security layer is in place. The following
capabilities are working:

| Capability | Status |
|---|---|
| YAML agent definition and validation | Complete |
| Anthropic SDK agentic loop | Complete |
| Verify-then-commit gate (y/n/edit) | Complete |
| Built-in tools (file, bash, web) | Complete |
| MCP stdio transport | Complete |
| Multi-agent handoff (`delegate_to_agent`) | Complete |
| CLI (`run`, `orchestrate`, `chat`, `list-tools`) | Complete |
| Structured audit logging (JSONL) | Complete |
| Path traversal prevention | Complete |
| Bash command blocklist (SI-3) | Complete |
| SSRF prevention for web fetch | Complete |
| Secret scrubbing in audit records | Complete |
| Session identity threading | Complete |
| Schema-validated YAML + policy checks | Complete |

**What is not yet implemented:**

- SSE transport for MCP servers (currently skips with a warning)
- Cryptographic signing of audit records (AU-10 non-repudiation)
- Log rotation and retention enforcement (AU-11 requires 1 year online)
- External SIEM forwarding
- Authentication for the CLI itself (assumes a trusted operator environment)

---

## 2. Architecture

```
main.py  (Typer CLI)
  └── creates SessionContext + AuditLogger  ← AU-2/AU-3/AU-8/AU-12
      └── Orchestrator
          ├── AgentLoader        (YAML → validated config)
          ├── PathEnforcer       (allowed_paths per agent)  ← AC-3/AC-6/AU-9
          ├── ToolRegistry       (enabled built-ins only)   ← AC-6/CM-7
          ├── MCPClientManager   (stdio connections)        ← AU-2/SC-28
          ├── VerificationGate   (y/n/edit before every tool call)
          │     ├── emits TOOL_CALL_PROPOSED                ← AU-12
          │     ├── emits VERIFICATION_DECISION             ← AU-12
          │     └── re-validates edited args                ← SI-10
          └── Agent  (agentic loop)
                ├── emits AGENT_TASK_START / END            ← AU-12
                ├── emits TOOL_EXECUTED                     ← AU-12
                └── calls tools via ToolRegistry / MCPClientManager
                      ├── PathEnforcer.check()              ← AC-3 → TOOL_ACCESS_DENIED
                      ├── validate_bash_command()           ← SI-3 → TOOL_BLOCKED
                      ├── validate_url() / SSRF check       ← SI-10/AC-3 → TOOL_BLOCKED
                      └── check_content_size()              ← SI-10 → TOOL_BLOCKED
```

### Data Flow: Tool Call

```
Model emits tool_use block
        ↓
VerificationGate.prompt()
  → logs TOOL_CALL_PROPOSED (with scrubbed args)     [AU-12 / SC-28]
  → shows REAL args to operator
  → operator chooses y / n / e
  → logs VERIFICATION_DECISION                       [AU-12]
        ↓ (approved)
ToolRegistry.call() / MCPClientManager.call_tool()
  → PathEnforcer.check(path)     → PermissionError → TOOL_ACCESS_DENIED  [AC-3]
  → validate_bash_command()      → ValueError      → TOOL_BLOCKED        [SI-3]
  → validate_url()               → ValueError      → TOOL_BLOCKED        [SI-10]
  → tool function executes
  → Agent logs TOOL_EXECUTED (with scrubbed result summary)              [AU-12 / SC-28]
        ↓
tool_result returned to model
```

---

## 3. File Structure

```
orchestration-framework/
├── main.py                        CLI entry point (Typer)
├── requirements.txt
│
├── agents/                        Example agent YAML definitions
│   ├── orchestrator.yaml          Multi-agent orchestrator
│   ├── researcher.yaml            Web research agent
│   └── coder.yaml                 Code writing / bash agent
│
├── framework/
│   ├── __init__.py
│   ├── agent.py                   Agentic loop, tool dispatch, AU-12 events
│   ├── audit_logger.py            Structured JSONL audit log (AU-2/3/8/9/12)
│   ├── input_validator.py         SI-3 bash blocklist, SI-10 size/SSRF checks
│   ├── mcp_client.py              MCP stdio connections, tool discovery
│   ├── orchestrator.py            Wires all components, handoff tool injection
│   ├── path_enforcer.py           Path traversal prevention (AC-3/AC-6/AU-9)
│   ├── schema.py                  YAML validation + FedRAMP policy checks
│   ├── secret_scrubber.py         Redacts secrets from audit records (SC-28)
│   ├── session.py                 Session identity for AU-3 attribution
│   ├── tool_registry.py           Built-in tool registry, AC-6 enforcement
│   └── verification.py            Verify-then-commit gate (human approval)
│
└── tools/
    ├── __init__.py
    ├── bash_tool.py               bash — SI-3 filtered, cwd confined
    ├── file_tools.py              read_file, write_file, list_dir — AC-3 enforced
    └── web_tools.py               web_fetch — SSRF blocked, http/https only
```

---

## 4. Installation

```bash
pip install -r requirements.txt
```

**Python 3.10+ required.**

Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Optionally set the audit log directory (defaults to `.audit_logs/` in CWD):

```bash
export AUDIT_LOG_DIR=/var/log/orchestration
```

---

## 5. CLI Usage

### Run a single agent on a task

```bash
python main.py run agents/researcher.yaml "Research the history of quantum computing"
```

With operator attribution (AU-3):

```bash
python main.py run agents/researcher.yaml "Research quantum computing" --operator "alice"
```

### Start a multi-agent orchestrated workflow

```bash
python main.py orchestrate agents/orchestrator.yaml "Build a Python web scraper"
```

### Interactive chat

```bash
python main.py chat agents/coder.yaml --operator "alice"
```

### List an agent's tools

```bash
python main.py list-tools agents/coder.yaml
```

All commands print the session ID and audit log path at startup:

```
Session: a3f1c2d4…  Audit log: .audit_logs/audit_a3f1c2d4_20260225.jsonl
```

---

## 6. YAML Agent Schema

```yaml
# Required fields
name: researcher
model: claude-opus-4-6
system_prompt: |
  You are a research agent...

# Optional metadata
description: Researches topics using web and files
operator: "alice"                   # AU-3: human identity for audit attribution

# Tools the agent can use
tools:
  builtin:
    - read_file                     # AC-6: only listed tools are available
    - write_file
    - list_dir
    - web_fetch
    - bash
  mcp:
    - name: filesystem
      transport: stdio              # only stdio currently supported
      command: npx
      args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
      env:                          # SC-28: passed to subprocess, never logged
        SOME_KEY: value

# AC-3/AC-6: filesystem confinement
allowed_paths:
  - /workspace/project             # agent may only read/write inside these dirs
                                   # defaults to CWD if omitted (logged as warning)

# AU-2/AU-3: audit configuration
audit:
  log_dir: ".audit_logs"           # where JSONL records are written
  max_result_chars: 500            # max chars of tool result in audit record

# Verification gate behavior
verification:
  mode: always                     # always | selective | never*
  require_for:                     # used in selective mode
    - bash
    - write_file
  # * 'never' mode is rejected at load time if bash or write_file are enabled

# Agent loop limit
max_turns: 20

# Multi-agent delegation
handoff:
  can_delegate_to:
    - researcher
    - coder
```

### Validation rules

- `name`, `model`, and `system_prompt` are required.
- `verification.mode: never` combined with `bash` or `write_file` raises a
  `ValueError` at load time (FedRAMP High policy — `CM-6`).
- Unknown top-level keys are rejected (`additionalProperties: false`).
- MCP server configs require `name`, `transport`, and `command`.

---

## 7. Verify-Then-Commit Gate

Every tool call the model proposes is shown to the operator before execution:

```
╭──── Tool Call Verification ────────────────────────────────────────╮
│  researcher wants to call: write_file                              │
│                                                                    │
│  {                                                                 │
│    "path": "notes/quantum.md",                                     │
│    "content": "# Quantum Computing\n\n..."                         │
│  }                                                                 │
╰────────────────────────────────────────────────────────────────────╯
  [y] Approve  [n] Deny  [e] Edit args >
```

| Choice | Behavior |
|---|---|
| `y` | Executes the tool with the displayed args |
| `n` | Returns `"User denied this tool call."` to the model |
| `e` | Prompts for new JSON args; re-validates against tool schema; re-confirms |

Tools that are auto-approved (in `selective` or `never` mode) still emit full
audit records — they are never silently executed.

---

## 8. Built-in Tools

| Tool | Description | Security Notes |
|---|---|---|
| `read_file(path)` | Read a file | Path must resolve inside `allowed_paths` |
| `write_file(path, content)` | Write a file | Path enforced; content capped at 10 MB |
| `list_dir(path)` | List directory | Path enforced |
| `bash(command, timeout)` | Run shell command | SI-3 blocklist runs before verification; cwd confined to first allowed root; timeout capped at 300s |
| `web_fetch(url, timeout)` | Fetch a URL | http/https only; SSRF blocked; no auto-redirect; response capped at 10 MB; timeout capped at 60s |

---

## 9. MCP Server Integration

Add an `mcp` block to any agent YAML:

```yaml
tools:
  mcp:
    - name: myserver
      transport: stdio
      command: npx
      args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
```

MCP tools are discovered at agent build time and formatted to Anthropic API
schema automatically. They flow through the same verification gate as built-in
tools. Responses are capped at 10 MB (SI-10).

**Note:** SSE transport is recognized in YAML but not yet implemented — it
logs a warning and is skipped.

---

## 10. Multi-Agent Handoff

Any agent with a `handoff.can_delegate_to` list gets a `delegate_to_agent` tool
injected automatically:

```
delegate_to_agent(agent, task, context="")
```

The orchestrator agent calls this tool; the verification gate prompts the
operator before the handoff executes; an `AGENT_HANDOFF` audit record is written.
Sub-agents have their own PathEnforcer and audit events, all correlated by the
same `session_id`.

---

## 11. Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required. Anthropic API credential. |
| `AUDIT_LOG_DIR` | `.audit_logs/` | Directory for audit JSONL files. |

---

## 12. FedRAMP High Controls

This section documents every NIST 800-53 Rev5 control implemented in the
framework, where it is implemented in the code, and why it matters.

---

### AU-2 — Auditable Events

**What the control requires:**
The organization must define the events that the system will audit. For
information systems at the High impact level, this includes all security-relevant
actions — not just failures.

**What is implemented:**
`framework/audit_logger.py` defines `AuditEventType`, an enum that catalogs
every event category the framework audits:

```
SESSION_START / SESSION_END
AGENT_TASK_START / AGENT_TASK_END
TOOL_CALL_PROPOSED
VERIFICATION_DECISION
TOOL_EXECUTED
TOOL_BLOCKED          (SI-3/SI-10 machine-level block)
TOOL_ACCESS_DENIED    (AC-3 path violation)
AGENT_HANDOFF
MCP_CONNECT / MCP_CONNECT_FAILED
VALIDATION_FAILED
```

Every path through the framework — including auto-approved tool calls,
denied tool calls, blocked commands, and path violations — produces a
distinct event type so that the audit record unambiguously describes what
happened.

**Why it matters:**
Without a defined event catalog, audit records are arbitrary and incomplete.
A FedRAMP assessor needs to verify that security-relevant events are
consistently captured. The enum makes the catalog explicit and code-enforced —
it cannot be bypassed by adding a new code path without also adding an event type.

---

### AU-3 — Content of Audit Records

**What the control requires:**
Each audit record must contain: timestamp, event type, subject (who), object
(what was acted upon), outcome, and location/source.

**What is implemented:**
Every record written by `AuditLogger.log()` contains:

```json
{
  "event_id":           "uuid4 — unique per record",
  "timestamp_utc":      "2026-02-25T14:32:01.123456+00:00",
  "session_id":         "uuid4 — ties all records in a session together",
  "event_type":         "TOOL_EXECUTED",
  "operator":           "alice",
  "agent_name":         "researcher",
  "model":              "claude-opus-4-6",
  "tool_name":          "write_file",
  "tool_input_scrubbed": {"path": "notes/q.md", "content": "..."},
  "outcome":            "success",
  "result_summary":     "Successfully wrote 1234 chars to notes/q.md"
}
```

The `operator` field comes from the `--operator` CLI flag and is stored in the
session. The `model` field records which Anthropic model proposed the tool call,
providing attribution even if the agent config is later changed. `result_summary`
is capped at 500 characters and run through the secret scrubber.

**Why it matters:**
Incomplete records are useless for forensic reconstruction. If an incident
occurs, a responder needs to answer: who ran what agent, which model proposed
which tool call, did a human approve it, and what was the result? AU-3 records
answer all of these questions from a single JSONL file.

---

### AU-8 — Time Stamps

**What the control requires:**
Audit records must use system clocks that produce UTC timestamps with at least
second-level granularity, in a consistent format.

**What is implemented:**
Every `AuditLogger.log()` call stamps the record using:

```python
datetime.now(timezone.utc).isoformat()
# → "2026-02-25T14:32:01.123456+00:00"
```

This produces an ISO 8601 timestamp with microsecond precision, explicitly
timezone-aware at UTC. The `+00:00` suffix is preserved so records are
unambiguous even if moved between systems with different local time settings.

**Why it matters:**
Correlating events across sessions, systems, or users requires timestamps that
are consistent and comparable. Timestamps without timezone information are
ambiguous and cannot be reliably sorted. At the High baseline, AU-8 is
non-negotiable — logs with local-time or epoch-only timestamps routinely cause
forensic failures.

---

### AU-9 — Protection of Audit Information

**What the control requires:**
The audit system must protect audit records from unauthorized access,
modification, and deletion — including by the subject being audited.

**What is implemented:**

**Append-only writes:** `AuditLogger.log()` opens the log file in `"a"` (append)
mode on every write and flushes immediately. The application never opens the file
for reading or seeking. There is no buffered write that could be lost on crash.

**Protected directory enforcement:** When `Orchestrator.build_agent()` creates a
`PathEnforcer` for an agent, it always passes the audit log directory as a
`protected_dir`:

```python
path_enforcer = PathEnforcer.from_config(
    allowed_paths=allowed_paths,
    protected_dirs=[audit_log_dir],   # AU-9
)
```

`PathEnforcer.check()` raises `PermissionError` if any file operation — even
one within an `allowed_path` — would resolve inside the audit log directory.
This means an agent using `write_file` or `bash` cannot overwrite or delete
audit records, even if its `allowed_paths` include the parent directory.

**Why it matters:**
A compromised or misbehaving agent that can overwrite its own audit log provides
no accountability. AU-9 is what separates a real audit trail from a log that
can be silently sanitized after an incident. The double protection (append-only
file semantics + PathEnforcer blocking) means the agent cannot tamper with logs
through either the write_file tool or a bash command.

---

### AU-12 — Audit Record Generation

**What the control requires:**
The system must generate audit records at the time each auditable event occurs,
from the components most closely associated with the event. Audit generation
must not be suppressible.

**What is implemented:**

**Synchronous writes at event time:** `AuditLogger.log()` writes and flushes
synchronously — there is no batching, no background thread, and no deferred
queue. If the write fails, it raises rather than continuing silently:

```python
with open(self._log_path, "a", encoding="utf-8") as f:
    f.write(line + "\n")
    f.flush()
```

**Two records per tool call:** `VerificationGate.prompt()` writes
`TOOL_CALL_PROPOSED` *before* showing anything to the operator (not after),
ensuring the record exists even if the operator kills the process during review.
`VERIFICATION_DECISION` is written after the operator responds. Neither record
can be omitted — the code path for auto-approved tools still calls `log()`.

**Always-on session records:** `AuditLogger.__init__()` writes `SESSION_START`
immediately on construction, and `close()` writes `SESSION_END`. Both are called
in `finally` blocks in `main.py` so they execute even on exception.

**Why it matters:**
Post-hoc audit record generation (writing logs after a batch of operations
completes) is insufficient for High systems. If the process crashes between an
action and its deferred log write, that action is unrecorded. AU-12 requires
generation at event time — the synchronous flush guarantees this. The
"before-show" placement of `TOOL_CALL_PROPOSED` means the audit record predates
the human decision, which is the correct causal ordering.

---

### AC-3 — Access Enforcement

**What the control requires:**
The system must enforce approved authorizations for logical access to information
and resources in accordance with applicable access control policies.

**What is implemented:**
`framework/path_enforcer.py` implements `PathEnforcer`, which is the AC-3
enforcement point for all file system access. Every file operation (read, write,
list) calls `path_enforcer.check(path, operation)` before doing any I/O:

```python
resolved = Path(path).resolve()   # resolves symlinks, normalizes ../ traversal

for protected in self.protected_dirs:
    if _is_relative_to(resolved, protected):
        raise PermissionError(...)   # AU-9: audit log protection

for root in self.allowed_roots:
    if _is_relative_to(resolved, root):
        return resolved              # access granted

raise PermissionError(...)           # not in any allowed root
```

The check uses `Path.resolve()` which follows symlinks, eliminating symlink
traversal attacks. The check also prevents `../` traversal — `../../etc/passwd`
resolves to `/etc/passwd` which is outside any workspace root.

The same principle applies to web fetch: `validate_url()` in
`input_validator.py` resolves the hostname via DNS and rejects any destination
that resolves to an RFC-1918 or loopback address (SSRF prevention):

```python
results = socket.getaddrinfo(hostname, None)
for (_, _, _, _, sockaddr) in results:
    ip = ipaddress.ip_address(sockaddr[0])
    if ip in _PRIVATE_NETWORKS:
        raise ValueError("AC-3/SI-10: SSRF blocked...")
```

Unresolvable hostnames are also rejected (fail-closed policy).

**Why it matters:**
Without AC-3 enforcement, a model that has been jailbroken or is hallucinating
file paths can read `/etc/shadow`, write to system directories, or pivot to
internal services via SSRF. The human verification gate helps, but it is not
a substitute for machine enforcement — a human reviewing `"path": "notes/q.md"`
may not notice that the shell has a working directory that makes this resolve
outside the workspace. `PathEnforcer` makes path confinement unconditional.

---

### AC-6 — Least Privilege

**What the control requires:**
The principle of least privilege: each subject is granted only the permissions
needed to accomplish its task, and no more.

**What is implemented:**

**Per-agent tool lists:** `ToolRegistry` is constructed with only the tools
listed in the agent's `tools.builtin` YAML array. A tool not in that list
cannot be called, even if the model hallucinates a call to it. The registry
raises `ValueError` at build time for unknown tool names.

**Per-agent path scope:** Each agent gets its own `PathEnforcer` built from
its own `allowed_paths` config. A researcher agent confined to `/workspace/research`
cannot read files in `/workspace/project` even if it is running on the same
machine as a coder agent with access to that directory.

**Tool factory binding:** Tool functions are closures bound to their agent's
`PathEnforcer` at construction time via factory functions (`make_file_functions`,
`make_bash_function`). This means the PathEnforcer is not a global — it is
baked into the callable itself, so it cannot be accidentally bypassed by a
different code path.

**Bash cwd confinement:** The `bash` tool runs with `cwd` set to the first
`allowed_root`, so relative paths inside commands are confined to the workspace
without relying on the command itself to use absolute paths.

**Why it matters:**
Least privilege is a foundational containment principle. If an agent is
compromised or misbehaving, its blast radius is limited to what it was actually
granted access to. An orchestrator agent that can only read/write files and
delegate to sub-agents cannot directly exfiltrate data via `web_fetch` — that
tool is not in its registry.

---

### CM-6 — Configuration Settings

**What the control requires:**
The organization must establish and document configuration settings that reflect
the most restrictive mode consistent with operational requirements, and enforce
those settings.

**What is implemented:**
`framework/schema.py` enforces configuration policy at agent load time. The
`check_high_risk_never_mode()` function runs after YAML validation:

```python
HIGH_RISK_TOOLS = {"bash", "write_file"}
if mode == "never" and HIGH_RISK_TOOLS & enabled_tools:
    raise ValueError("FedRAMP High policy violation: verification mode 'never'...")
```

This means the YAML file itself cannot express a configuration that violates
the security policy. The error is raised before the agent runs — there is no
way to use the framework to run `bash` or `write_file` without human review.

The schema also uses `additionalProperties: False`, which means unknown keys in
agent YAML are rejected rather than silently ignored. This prevents configuration
drift where a deprecated security field is retained in YAML but no longer
read by the code.

**Why it matters:**
Security settings that can be misconfigured are settings that will eventually
be misconfigured. CM-6 requires that the system enforce its own security
baseline rather than relying on operators to remember every constraint. Making
`verification.mode: never` + high-risk tools a hard error at load time means
no agent definition can accidentally or deliberately bypass the human approval
requirement.

---

### SC-8 — Transmission Confidentiality and Integrity

**What the control requires:**
The system must protect the confidentiality and integrity of transmitted
information.

**What is implemented:**
`web_fetch` only allows `http` and `https` schemes:

```python
_ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})
if scheme not in _ALLOWED_SCHEMES:
    raise ValueError("SI-10/SC-8: URL scheme not permitted...")
```

This blocks `file://` (local file exfiltration), `ftp://`, `gopher://`,
`data://`, and `javascript://` URIs. HTTPS is the only scheme that provides
both confidentiality and integrity; `http` is allowed but logged.

The Anthropic API client uses HTTPS by default (enforced by the `anthropic`
SDK), so all model API calls are encrypted in transit.

**Why it matters:**
Allowing arbitrary URL schemes creates exfiltration and SSRF attack surfaces
that are invisible to a human reviewing just the hostname. A `file:///etc/shadow`
URL would bypass SSRF IP checks entirely. Restricting to http/https closes this
class of attack.

---

### SC-28 — Protection of Information at Rest

**What the control requires:**
The system must protect the confidentiality and integrity of information at rest
— including in log files.

**What is implemented:**
`framework/secret_scrubber.py` provides three scrubbing functions used throughout
the framework:

- `scrub_string(s)` — applies named regex patterns to detect and replace API
  keys, bearer tokens, PEM private keys, and password assignments.
- `scrub_dict(data)` — recursively scrubs dict/list structures; any key whose
  name matches a sensitive pattern (password, token, api_key, secret, etc.)
  has its value replaced with `[REDACTED:sensitive_key]` regardless of content.
- `scrub_url(url)` — redacts sensitive query parameter values (token, api_key,
  client_secret, etc.) before URLs are written to audit records.

The scrubber is applied at two points:

1. **VerificationGate:** `TOOL_CALL_PROPOSED` and `VERIFICATION_DECISION` records
   receive `scrub_dict(tool_input)` — secrets in args are redacted before writing.
   The console shows real args to the operator (who is authorized to see them).

2. **Agent:** `TOOL_EXECUTED` records receive `scrub_string(result[:500])` —
   tool results are truncated and scrubbed before the summary is written to the log.

MCP server `env` blocks are explicitly never included in `MCP_CONNECT` audit
records, even though they are passed to the subprocess. This prevents API keys
in MCP server environment variables from appearing in logs.

**Why it matters:**
Log files are frequently shared — with auditors, incident responders, monitoring
systems, and SIEM tools. A log file containing an Anthropic API key is a
credential leak. SC-28 at the High baseline requires protection of all sensitive
data at rest, and audit logs are "at rest" the moment they are written. The
named-pattern approach (`[REDACTED:anthropic_api_key]`) is preferable to simple
deletion because the redaction is itself visible in the log, which lets
responders know a credential was present without exposing the credential.

---

### SI-3 — Malicious Code Protection

**What the control requires:**
The system must employ malicious code protection mechanisms at appropriate
locations, and update those mechanisms when new releases are available. At the
High baseline, the system must be able to detect and respond to malicious code
without relying solely on user review.

**What is implemented:**
`framework/input_validator.py` defines `_BASH_BLOCKLIST`, a list of compiled
regex patterns matched against every bash command *before* the human verification
gate is shown:

```python
_BASH_BLOCKLIST = [
    (re.compile(r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+|--force\s+)?/"),  "rm of root-anchored path"),
    (re.compile(r"\bmkfs\b"),                                          "filesystem format"),
    (re.compile(r"\bdd\b.*\bof=/dev/"),                                "raw device write via dd"),
    (re.compile(r":\(\)\s*\{.*\}.*:"),                                 "fork bomb"),
    (re.compile(r"\bcurl\b[^|]*\|\s*(bash|sh|python3?)"),             "curl pipe-to-shell"),
    ...
]
```

If the command matches any pattern, `validate_bash_command()` raises `ValueError`
with a descriptive message tagged `SI-3:`. This exception propagates through
`ToolRegistry.call()`, which logs a `TOOL_BLOCKED` audit event and returns an
error string to the model. The human verification gate is never shown — the
block is unconditional.

**Why it matters:**
The verify-then-commit gate is a strong control, but it depends on the operator
reading every command carefully. A sophisticated jailbreak might construct a
command that appears benign at first glance but is destructive (e.g., obfuscated
fork bombs, commands that look like a path but include `rm -rf /`). SI-3 at
the High baseline explicitly requires that protection mechanisms operate
*in addition to* human review, not as a substitute for it. The blocklist
provides this second layer. Even if an operator approves a command, the blocklist
catches patterns that no reasonable operator would intentionally approve.

---

### SI-10 — Information Input Validation

**What the control requires:**
The system must check the validity of all inputs — both from users and from
external sources — and reject inputs that do not meet defined criteria.

**What is implemented:**
`framework/input_validator.py` provides validators applied at every tool input
boundary:

**URL validation (`validate_url`):**
- Rejects URLs longer than 2,048 characters
- Rejects non-http(s) schemes
- Rejects URLs with no hostname
- Resolves the hostname via DNS and rejects RFC-1918 / loopback destinations
- Fails closed on DNS resolution errors

**Bash validation (`validate_bash_command`):**
- Rejects commands longer than 4,096 characters
- Applies SI-3 blocklist patterns (see above)

**Timeout validation (`validate_bash_timeout`):**
- Caps bash timeout at 300 seconds — prevents `timeout=86400` from creating a
  process that runs indefinitely and evades human oversight

**Content size validation (`check_content_size`):**
- Rejects `write_file` content larger than 10 MB
- Rejects web fetch responses larger than 10 MB
- Rejects MCP tool responses larger than 10 MB

**Post-edit re-validation (`validate_tool_args`):**
- When an operator edits tool args via the `[e]` path in the verification gate,
  the edited JSON is re-validated against the tool's declared `input_schema`
  before acceptance. This prevents an operator from accidentally (or deliberately)
  injecting args of the wrong type that could cause unexpected behavior in the
  tool function.

**Why it matters:**
AI models can be prompted to produce inputs that exploit unexpected behavior in
downstream tool functions. A 500 MB `content` argument to `write_file` is a
denial-of-service attack against disk space. A `file://` URL to `web_fetch` is
a local file read. A command with 100,000 characters may be intended to overflow
a regex engine or a shell parser. SI-10 requires validation at every boundary —
the framework validates at the point of tool invocation, not after.

---

## Audit Record Example

A complete session produces records like the following in `.audit_logs/audit_<id>_<date>.jsonl`:

```jsonl
{"event_id":"a1b2c3d4-...","timestamp_utc":"2026-02-25T14:32:00.001Z","session_id":"e5f6...","event_type":"SESSION_START","operator":"alice"}
{"event_id":"b2c3d4e5-...","timestamp_utc":"2026-02-25T14:32:00.500Z","session_id":"e5f6...","event_type":"AGENT_TASK_START","agent_name":"researcher","model":"claude-opus-4-6","task_summary":"Research quantum computing"}
{"event_id":"c3d4e5f6-...","timestamp_utc":"2026-02-25T14:32:05.120Z","session_id":"e5f6...","event_type":"TOOL_CALL_PROPOSED","agent_name":"researcher","model":"claude-opus-4-6","tool_name":"web_fetch","tool_input_scrubbed":{"url":"https://en.wikipedia.org/wiki/Quantum_computing"}}
{"event_id":"d4e5f6a7-...","timestamp_utc":"2026-02-25T14:32:08.440Z","session_id":"e5f6...","event_type":"VERIFICATION_DECISION","agent_name":"researcher","tool_name":"web_fetch","verification_choice":"y","outcome":"approved"}
{"event_id":"e5f6a7b8-...","timestamp_utc":"2026-02-25T14:32:12.900Z","session_id":"e5f6...","event_type":"TOOL_EXECUTED","agent_name":"researcher","model":"claude-opus-4-6","tool_name":"web_fetch","tool_input_scrubbed":{"url":"https://en.wikipedia.org/wiki/Quantum_computing"},"outcome":"success","result_summary":"[Status: 200] [Content-Type: text/html..."}
{"event_id":"f6a7b8c9-...","timestamp_utc":"2026-02-25T14:32:45.001Z","session_id":"e5f6...","event_type":"AGENT_TASK_END","agent_name":"researcher","model":"claude-opus-4-6","turns_used":4,"outcome":"completed"}
{"event_id":"a7b8c9d0-...","timestamp_utc":"2026-02-25T14:32:45.020Z","session_id":"e5f6...","event_type":"SESSION_END","operator":"alice"}
```
