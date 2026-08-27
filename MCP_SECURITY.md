# MCP Security Guide

Security and compliance auditing for MCP servers before they reach production.

## Problem

The Model Context Protocol lets AI agents call external tools, APIs, databases, and files. That power creates new risks: secrets in code, dangerous tool capabilities, unvalidated input, excessive data exposure, and weak access controls. Manual review is slow and easy to miss MCP-specific issues that generic scanners overlook.

## Solution

A lightweight MCP security scanner that developers run against a server repository or deployment:

```bash
mcp-guard ./my-mcp-server
mcp-guard ./my-mcp-server --format json
mcp-guard . --fail-on high          # CI gate
mcp-guard ./server --live           # optional: inspect running /mcp endpoint
mcp-guard ./server --ai             # optional: contextual explanations
```

Pipeline:

```
MCP server (source or live endpoint)
        ↓
Static analysis + MCP-aware inspection
        ↓
Security rules (deterministic)
        ↓
Optional AI review (structured findings only)
        ↓
Optional adversarial tests
        ↓
Risk score → PASS / REVIEW / FAIL
        ↓
Report (Markdown / JSON)
```

Core value: identify dangerous MCP capabilities before deployment. This is **not** a replacement for professional penetration testing or a full security audit.

---

## Capabilities

### A — Static security analysis

Scan source and configuration for:

- Hard-coded API keys, passwords, tokens
- Dangerous shell execution (`subprocess`, `shell=True`, eval)
- Suspicious URLs, insecure HTTP, debug mode enabled
- Missing environment-based configuration
- Overly broad filesystem or network access

### B — MCP-specific analysis

Treat the project as an MCP server, not generic Python/Node code. Inspect:

- Tool names, descriptions, and input/output schemas
- Resources, prompts, and declared capabilities
- Tool handlers: what each tool can read, write, or execute
- Authentication and authorization on the MCP transport
- Data minimization: does each tool return only what it needs?

Example finding:

```
Tool: execute_command
Severity: CRITICAL
Reason: Arbitrary command execution with no allowlist or authorization.
```

For Python MCP servers, analysis covers `@mcp.tool` handlers, `MCPServer` transport settings, and the chat/agent boundary.

---

## Security rules

Twelve focused rules beat dozens of shallow ones.

| ID | Severity | Rule |
|----|----------|------|
| MCP001 | CRITICAL | Hard-coded secret in source or committed config |
| MCP002 | CRITICAL | Arbitrary command execution from user or model input |
| MCP003 | CRITICAL | Unrestricted dangerous tool without authorization |
| MCP004 | INFO | MCP authentication requires live/deploy verification (not inferred from config keys) |
| MCP005 | HIGH | User-controlled input reaches dangerous operations unvalidated |
| MCP006 | HIGH | Tool returns significantly more data than required |
| MCP007 | HIGH | Path traversal or unrestricted file access |
| MCP008 | MEDIUM | Missing rate limiting |
| MCP009 | MEDIUM | Missing audit logging for sensitive operations |
| MCP010 | MEDIUM | Insecure HTTP endpoint (no TLS in production) |
| MCP011 | MEDIUM | Debug mode enabled |
| MCP012 | MEDIUM | Missing or weak tool input schema |

Additional rules worth adding for agent-backed gateways:

| ID | Severity | Rule |
|----|----------|------|
| MCP013 | HIGH | PII or financial fields exposed beyond lookup need |
| MCP014 | HIGH | Missing tenant or scope isolation on tool results |
| MCP015 | HIGH | Chat/agent layer can call MCP with no auth boundary |

---

## Risk scoring

| Severity | Points |
|----------|--------|
| CRITICAL | 25 |
| HIGH | 15 |
| MEDIUM | 8 |
| LOW | 3 |

- Any **CRITICAL** finding → automatic **FAIL**
- Score = `max(0, 100 − sum(points))`, capped at 100
- **90–100** PASS · **70–89** REVIEW · **0–69** FAIL

Example report header:

```
Security Score: 64/100
Status:         FAIL
Critical:       1
High:           2
Medium:         3
Low:            0
```

---

## CI integration

```yaml
- name: MCP Security Scan
  run: uv run python mcp_guard.py . --fail-on high
```

---

## Applying this to financial-mcp-gateway

Current demo posture (appropriate for local dev, not production):

| Area | Status |
|------|--------|
| Read-only MCP tools | Good — no writes/transfers via tools |
| Structured tool schemas | Good — `structured_output=True`, `ToolError` |
| Chat input guardrails | Partial — regex blocks in `schema.py` + prompt rules |
| MCP authentication | Gap — OAuth config exists but server does not enforce it |
| Chat → MCP boundary | Gap — unauthenticated `/chat` drives tool calls |
| Transport | Gap — HTTP on `0.0.0.0`, no TLS |
| Data minimization | Gap — balance tool returns extra customer metadata |
| Rate limiting / audit | Gap — not implemented |

Hardening priorities: enforce auth on MCP and chat, TLS, rate limits, trim tool payloads, structured audit logs.
