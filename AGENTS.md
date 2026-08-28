# AGENTS.md

Guidelines for AI coding agents contributing to the **Financial MCP Gateway** — a reference implementation built for the [AAIF Ambassadors MCP Education Campaign](https://github.com/habeneyasu/financial-mcp-gateway).

For project setup and architecture, see [README.md](./README.md).

---

## Purpose of This File

This file instructs AI coding agents on the architectural rules, boundaries, and contribution standards for this repository. It operates at development time — complementing the runtime capability boundary enforced by MCP itself.

The combination is intentional:

- **MCP** enforces what the agent can access at runtime.
- **AGENTS.md** enforces how the codebase should be structured during development.

---

## Core Invariant

> **Financial data reaches the agent only through MCP tools — never through domain services, `db.py`, SQLite, or financial REST calls from `agent/`.**

This boundary is not a suggestion. It is the central architectural principle of this project and must be preserved in all contributions.

The required path is:

```text
Agent
  ↓  (tool selection)
MCP Client          client.py
  ↓  (HTTP POST /mcp)
MCP Server          server.py
  ↓
MCP Tool            mcp/
  ↓
Domain Service      accounts/, customers/, …
  ↓
Database            SQLite
```

Gemini **selects** tools. `client.py` **invokes** them. Neither accesses domain services or the database directly.

---

## Codebase Layers

| Path | Responsibility |
|---|---|
| `src/financial_mcp_gateway/agent/` | Agent orchestration, Gemini integration, prompts, input/output guardrails |
| `src/financial_mcp_gateway/mcp/` | MCP tool definitions — thin handlers that delegate to domain services |
| `src/financial_mcp_gateway/accounts/` | Account domain logic |
| `src/financial_mcp_gateway/customers/` | Customer domain logic |
| `src/financial_mcp_gateway/transactions/` | Transaction domain logic |
| `src/financial_mcp_gateway/users/` | User domain logic |
| `src/financial_mcp_gateway/idempotency/` | Idempotency domain logic |
| `src/financial_mcp_gateway/api/` | REST API — parallel interface for non-agent clients |
| `client.py` | MCP client (Streamable HTTP, MCP 2026-07-28) |
| `db.py` | SQLite schema, seed data, and persistence |
| `config.py` | Environment-driven configuration |

### Agent Boundary

Code under `src/financial_mcp_gateway/agent/` must not import or directly access:

- Domain services (accounts, customers, transactions, users)
- `db.py` or any SQLite/database driver
- Financial REST endpoints

Violations break the MCP capability boundary and undermine the purpose of this project.

---

## Where to Make Changes

| Change | Location |
|---|---|
| New financial capability | Domain service → MCP tool handler in `mcp/` |
| Input/output size limits | `agent/schema.py` |
| Agent reply behavior and examples | `agent/prompts.py` |
| Tool orchestration and loop logic | `agent/agent.py` |
| LLM integration and wire format | `agent/llm.py` |
| Tool-call round limit | `AGENT_MAX_TOOL_ROUNDS` in `.env` or `config.py` |
| Chat UI and HTTP behavior | `chat_app.py` |

**Principles:**
- Business logic belongs in domain services, not in MCP handlers, prompts, or agent code.
- MCP tool handlers must remain thin — validate inputs, call a domain service, return a typed result.
- Prompts are behavioral guidance, not security controls. Security-sensitive restrictions must be enforced in code.

---

## Adding a Financial Capability

Follow this pattern without exception:

```text
1. Implement business logic in the domain service
2. Define a typed MCP tool in mcp/ that delegates to the service
3. The tool becomes discoverable via tools/list
4. The agent invokes it via tools/call
```

Tools must be:

- **Narrow** — one purpose per tool
- **Typed** — structured Pydantic inputs and outputs
- **Read-only** — no financial mutations without explicit design review
- **Honest** — return structured errors rather than masking failures

Do not expose generic capabilities such as SQL execution or unrestricted API calls. Each tool should represent a named, intentional financial capability.

---

## Agent Behavior Standards

The agent must:

- Use MCP tools as the sole source of financial facts
- Treat tool results as ground truth — never infer or invent financial data
- Report tool failures honestly to the user
- Respect the read-only scope of the current tool catalog
- Stay within `AGENT_MAX_TOOL_ROUNDS` per request (default: 8)

---

## Contribution Standards

This repository is part of the **AAIF Ambassadors MCP Education Campaign**. Contributions should reflect the quality and clarity expected of a published reference implementation.

Before submitting changes, run the test suite:

```bash
uv run pytest
```

Then verify the following:

- [ ] The MCP capability boundary is preserved — agent has no direct domain or database access
- [ ] New financial capabilities are exposed through MCP tools, not injected into the agent
- [ ] MCP tool handlers are thin and delegate to domain services
- [ ] Tools are narrow, typed, structured, and read-only
- [ ] Business logic resides in domain services
- [ ] All tests pass
- [ ] `README.md` is updated if architecture, endpoints, or tools change
- [ ] No secrets, credentials, or sensitive configuration are introduced or logged

---

## Architectural Rule

When in doubt, apply this rule:

```text
AI Agent
    │
    │  MCP (capability boundary)
    ▼
Financial Capabilities
    │
    ▼
Domain Services  (business logic)
    │
    ▼
Data
```

> **The agent reasons. MCP exposes capabilities. Domain services own the business logic.**

This separation is what makes the system trustworthy, testable, and extensible.
