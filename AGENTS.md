# AGENTS.md

Rules for AI coding agents working on **Financial MCP Gateway**.

For setup and architecture, see [README.md](./README.md).  
For security rules, see [MCP_SECURITY.md](./MCP_SECURITY.md).

---

## Invariant

> **Financial data reaches the agent only through MCP tools — never through domain services, `db.py`, SQLite, or financial REST calls from `agent/`.**

The intended path is:

```text
Agent
  ↓
MCP Client
  ↓
MCP Server
  ↓
MCP Tool
  ↓
Domain Service
  ↓
Database
```

Gemini **selects** tools. `client.py` **invokes** them through MCP:

```text
tools/list → tools/call
```

Do not introduce a path that allows the agent to bypass MCP.

---

## Layers

| Path | Responsibility |
|---|---|
| `src/financial_mcp_gateway/agent/` | Agent orchestration, Gemini integration, prompts, guardrails |
| `src/financial_mcp_gateway/mcp/` | MCP tool definitions and handlers |
| `src/financial_mcp_gateway/accounts/` | Account domain logic |
| `src/financial_mcp_gateway/customers/` | Customer domain logic |
| `src/financial_mcp_gateway/transactions/` | Transaction domain logic |
| `src/financial_mcp_gateway/users/` | User domain logic |
| `src/financial_mcp_gateway/idempotency/` | Idempotency domain logic |
| `src/financial_mcp_gateway/api/` | REST API; separate from the agent path |
| `client.py` | MCP client using Streamable HTTP |
| `mcp_guard.py` | Static MCP boundary and security checks |
| `db.py` | SQLite schema, seed data, and persistence |

### Agent boundary

Code under:

```text
src/financial_mcp_gateway/agent/
```

must not import or directly access:

- Domain services
- `db.py`
- SQLite
- Database drivers
- Financial REST endpoints

---

## Where to Change What

| Change | Location |
|---|---|
| New financial capability | Domain service → MCP tool |
| Hard input/output limits | `agent/schema.py` |
| Reply behavior and examples | `agent/prompts.py` |
| Tool orchestration | `agent/agent.py` |
| Gemini integration / wire format | `agent/llm.py` |
| Tool-call round limit | `AGENT_MAX_TOOL_ROUNDS` |
| HTTP / Gradio behavior | `chat_app.py` |
| MCP security rules | `mcp_guard.py`, `MCP_SECURITY.md` |

**Business logic belongs in domain services.**

**MCP handlers should remain thin and delegate to domain services.**

**Prompts are not a security boundary.** Security-sensitive restrictions must be enforced in code.

---

## Adding a Financial Capability

Follow this pattern:

```text
Domain Service
      ↓
MCP Tool
      ↓
tools/list
      ↓
Agent discovers capability
      ↓
tools/call
```

Keep tools:

- Narrow
- Purpose-specific
- Typed
- Structured
- Read-only

Do not implement financial business logic in the agent, prompts, or MCP handlers.

---

## Do Not

- Bypass MCP from `agent/`.
- Import domain services from `agent/`.
- Access `db.py`, SQLite, or database drivers from `agent/`.
- Call financial REST endpoints directly from `agent/`.
- Put business logic in prompts, agent code, or MCP handlers.
- Add write/mutation tools without explicit security design and documentation.
- Weaken validation or tool-loop limits without justification.
- Commit secrets.
- Expose credentials or sensitive configuration in logs or tool output.

---

## Agent Behavior

The agent must:

- Use MCP tools for financial facts.
- Treat tool results as the source of truth.
- Never invent balances, transactions, customers, or other financial data.
- Report tool failures honestly.
- Respect the read-only scope.
- Stay within `AGENT_MAX_TOOL_ROUNDS`.

---

## Before Submitting Changes

Run:

```bash
uv run pytest
uv run python mcp_guard.py . --fail-on high
```

Then verify:

- [ ] MCP boundary is preserved.
- [ ] Agent has no direct domain or database access.
- [ ] New financial capabilities are exposed through MCP.
- [ ] Tools are narrow, typed, structured, and read-only.
- [ ] Business logic remains in domain services.
- [ ] Tests pass.
- [ ] Security checks pass.
- [ ] `README.md` or `MCP_SECURITY.md` is updated when architecture or security behavior changes.
- [ ] No secrets or credentials were introduced.

---

## Local Workflow

With Docker Compose (MCP + chat + REST):

```bash
docker compose up --build
```

Or run locally:

```bash
uv run python server.py
uv run python chat_app.py
```

Endpoints:

```text
MCP   → http://127.0.0.1:8000/mcp
Chat  → http://127.0.0.1:8001/
```

Agent entry point:

```text
financial_mcp_gateway.agent.chat
```

Chat API:

```text
POST /chat
```

---

## Architectural Rule

When in doubt, preserve this boundary:

```text
AI Agent
    │
    │ MCP
    ▼
Financial Capabilities
    │
    ▼
Domain Services
    │
    ▼
Data
```

**The agent reasons. MCP exposes capabilities. Domain services own the business logic.**