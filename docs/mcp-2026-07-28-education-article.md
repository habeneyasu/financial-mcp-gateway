# Building a Financial MCP Gateway on MCP 2026-07-28

**A migration diary, architecture walkthrough, and demo repository for the AAIF Ambassadors MCP Education Campaign**

**Repository:** [github.com/habeneyasu/financial-mcp-gateway](https://github.com/habeneyasu/financial-mcp-gateway)

---

## 1. Why This Article?

The [AAIF Ambassadors MCP 2026-07-28 Education Campaign](https://modelcontextprotocol.io) asks contributors to help others understand one of the biggest MCP releases yet. I am contributing in two ways:

1. **This article** — a migration diary explaining how I built and used a financial MCP gateway on the new specification.
2. **A demo repository** — a runnable project others can clone, extend, and learn from.

Financial systems already expose APIs. Agents raise a different question: **how do you grant access to capabilities without granting access to the system?** This article documents the answer I implemented — putting MCP between the agent and the financial domain — and why MCP 2026-07-28 is the right foundation for that design.

---

## 2. What Problem Does It Solve?

### The core problem

When you connect an LLM to a financial backend, three risks appear immediately:

| Risk | What goes wrong |
|------|-----------------|
| **Over-access** | The agent inherits full backend power — writes, admin APIs, raw database queries |
| **Hallucination** | The model invents balances, transactions, or customer records when it lacks data |
| **No audit trail** | Tool calls are ad hoc; there is no standard contract for what the agent can request |

Consider a simple user question:

```text
What is the balance for acc-1?
```

A correct answer requires real data. But the agent must also:

- Never bypass access controls
- Never invent financial facts
- Stay within a bounded, read-only scope
- Return results through a inspectable, typed interface

Giving the LLM direct access to SQLite, domain services, or internal REST endpoints fails all four requirements.

### The design goal

> **Financial data reaches the agent only through MCP tools — never through domain services, `db.py`, SQLite, or financial REST calls from the agent layer.**

This is not just a prompt instruction. It is an architectural invariant enforced in code and verified by a static security scanner.

---

## 3. What Approach Did I Use?

I chose a **capability-boundary architecture** with three parallel interfaces over one shared domain:

```text
                    ┌─────────────────┐
                    │   Gemini Chat   │  ← agent path (via MCP only)
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   MCP Client    │  tools/list → tools/call
                    └────────┬────────┘
                             │
┌──────────────┐    ┌────────▼────────┐    ┌──────────────┐
│ MCP Clients  │───▶│   MCP Server    │    │   REST API   │
└──────────────┘    └────────┬────────┘    └──────┬───────┘
                             │                     │
                    ┌────────▼─────────────────────▼───┐
                    │         Domain Services          │
                    └────────┬─────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │     SQLite      │
                    └─────────────────┘
```

**Why this shape?**

- **MCP** is the standard agent interface — named tools, typed arguments, structured responses.
- **REST** serves traditional integrations without forcing every consumer through an LLM.
- **Chat** demonstrates the full agent loop (Gemini + MCP) for education and testing.
- **Domain services** own business logic once; MCP handlers stay thin delegates.

The agent path is deliberately narrow. Gemini **selects** tools; `client.py` **invokes** them through MCP. The model never imports domain code or queries the database directly.

---

## 4. Why MCP 2026-07-28?

The [MCP 2026-07-28 specification](https://modelcontextprotocol.io/specification/2026-07-28) is not a cosmetic version bump. Three changes directly shaped this project:

### Streamable HTTP

Earlier MCP setups often relied on SSE-heavy or ad hoc HTTP wiring. MCP 2026-07-28 treats **Streamable HTTP** as the primary transport.

```python
# server.py
mcp.run(
    transport="streamable-http",
    host="0.0.0.0",
    port=config.PORT,
    streamable_http_path=config.MCP_PATH,
    stateless_http=True,
    json_response=True,
)
```

**Why it matters:** A single HTTP endpoint (`/mcp`) deploys cleanly behind Docker, load balancers, and standard HTTP tooling. No special streaming client setup is required for basic `tools/list` and `tools/call` operations.

### Structured tool inputs and outputs

Every financial tool declares `structured_output=True` and returns a Pydantic model:

```python
# src/financial_mcp_gateway/mcp/accounts.py
@mcp.tool(
    title="Get account balance",
    description="Return balance and metadata for a financial account.",
    structured_output=True,
)
async def get_account_balance(account_id: str) -> AccountBalanceOutput:
    def _run() -> AccountBalanceOutput:
        account = service.get_account_balance_details(account_id)
        return AccountBalanceOutput(
            account_id=account["id"],
            customer=AccountBalanceCustomer(
                id=account["customer_id"],
                first_name=account["customer_first_name"],
                last_name=account["customer_last_name"],
            ),
            balance=format_amount(account["balance_cents"]),
            transaction_count=account["transaction_count"],
            # ...
        )
    return run_tool(_run, not_found=(AccountNotFound, "account_not_found"))
```

**Why it matters:** Tool results are predictable, machine-readable objects — not free-form strings the model must parse. That improves agent reliability and makes outputs easier to validate, test, and audit.

Example structured response from `get_account_balance`:

```json
{
  "account_id": "acc-1",
  "customer": { "id": "cust-1", "first_name": "Alice", "last_name": "Nguyen" },
  "account_number": "1000000001",
  "account_type": "checking",
  "name": "Operating",
  "currency": "USD",
  "status": "active",
  "balance": "1250000.00",
  "transaction_count": 3
}
```

### Protocol-aware SDK (`mcp` 2.0)

Both client and server target the same protocol version explicitly:

```python
# config.py
MCP_MODERN_PROTOCOL_VERSION = "2026-07-28"

# client.py
self._client = Client(self.url, mode=MCP_MODERN_PROTOCOL_VERSION)
```

**Why it matters:** Migration is not just bumping a dependency. Transport, schemas, and SDK behavior must align around one specification. Pinning `2026-07-28` on both sides removes ambiguity.

| Area | Earlier patterns | MCP 2026-07-28 in this demo |
|------|------------------|----------------------------|
| Transport | SSE-heavy or ad hoc HTTP | Streamable HTTP |
| Tool contracts | Loosely typed text | Structured Pydantic I/O |
| SDK | Pre-2.0 APIs | `mcp` 2.0 + `mcp-types` 2.0 |

---

## 5. MCP + AGENTS.md: How They Complement Each Other

[MCP](https://modelcontextprotocol.io) defines **how agents call external capabilities**. [`AGENTS.md`](../AGENTS.md) defines **how AI coding agents must behave when modifying this repository**. They solve different problems but reinforce the same boundary.

### MCP: runtime capability boundary

At runtime, MCP controls what the *financial assistant* can do:

- Which tools exist (`tools/list`)
- What arguments they accept (typed schemas)
- What structured data they return (`structured_output=True`)

### AGENTS.md: development-time architectural guardrails

At development time, `AGENTS.md` controls what *coding agents* (Cursor, Copilot, etc.) must not break:

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

Key rules from `AGENTS.md`:

| Rule | Why |
|------|-----|
| Code under `agent/` must not import domain services, `db.py`, or SQLite | Prevents a shortcut that bypasses MCP at runtime |
| New capabilities follow `Domain Service → MCP Tool` | Keeps business logic out of the agent layer |
| Prompts are not a security boundary | Behavioral guidance ≠ enforcement |
| Run `mcp_guard.py` before submitting changes | Catches boundary violations statically |

### How they work together

```text
┌─────────────────────────────────────────────────────────────┐
│  AGENTS.md (build time)                                     │
│  "Don't let coding agents bypass MCP when editing code"     │
└──────────────────────────┬──────────────────────────────────┘
                           │ enforced by mcp_guard.py + review
┌──────────────────────────▼──────────────────────────────────┐
│  MCP (runtime)                                              │
│  "The financial assistant can only call declared tools"     │
└─────────────────────────────────────────────────────────────┘
```

**Example:** A coding agent might suggest importing `AccountService` directly in `agent/agent.py` for convenience. `AGENTS.md` forbids it. `mcp_guard.py` flags the import. At runtime, even if that import slipped through, the production agent loop only calls tools through `GatewayMCPClient.call_tool()`.

MCP protects users. `AGENTS.md` protects the architecture that makes MCP protection possible.

---

## 6. Overall System Architecture

Three interfaces, one shared domain:

| Interface | Role | URL |
|-----------|------|-----|
| **MCP** | Agents and MCP clients | `http://127.0.0.1:8000/mcp` |
| **Gemini Chat** | Gradio UI + `POST /chat` | `http://127.0.0.1:8001/` |
| **REST** | Traditional integrations (optional) | `http://127.0.0.1:8080/docs` |

### End-to-end chat flow

```text
User
  → Input guardrails (Pydantic + policy checks)
  → Agent orchestration (agent/agent.py)
  → Gemini API (tool selection / reply)
  → MCP Client (tools/list → tools/call)
  → MCP Server → Tool handlers
  → Domain Services → SQLite
  → Structured tool results → Gemini
  → Output guardrails
  → User
```

### Why separate MCP from REST?

REST and MCP share domain services, but they serve different consumers:

- **REST clients** expect OpenAPI, HTTP verbs, and integration patterns they already know.
- **Agent clients** expect `tools/list` and `tools/call` with structured schemas.

Only the agent path routes through MCP. This keeps the MCP surface narrow and purpose-built for LLM tool calling, while REST remains available for non-agent integrations.

---

## 7. Inside the MCP Layer

The MCP layer is intentionally thin. Handlers delegate to domain services; they do not contain business logic.

### Tool registration

All tools are registered at server startup:

```python
# src/financial_mcp_gateway/mcp/__init__.py
def register_tools(mcp: MCPServer) -> None:
    register_customer_tools(mcp)
    register_account_tools(mcp)
    register_transaction_tools(mcp)
    register_user_tools(mcp)
    register_idempotency_tools(mcp)
```

### Read-only tool catalog

| Tool | Purpose |
|------|---------|
| `get_customer` | Lookup customer by ID |
| `get_account` | Account details |
| `get_account_balance` | Balance + metadata |
| `get_transactions` | Recent transactions for an account |
| `get_transaction_summary` | System-wide counts by status |
| `get_transaction` | Single transaction by reference |
| `get_user` | User lookup |
| `list_users` | Users for a customer |

**Why read-only only?** Write tools (transfers, payments) require idempotency, authorization, audit logging, and adversarial testing. This demo focuses on the read path and the MCP boundary. Adding mutation tools would need explicit security design — documented in `MCP_SECURITY.md`.

### Error handling with `ToolError`

Domain failures map to MCP tool errors instead of leaking stack traces:

```python
# src/financial_mcp_gateway/mcp/helpers.py
def run_tool(fn, *, not_found=None):
    try:
        return fn()
    except Exception as exc:
        if not_found and isinstance(exc, not_found[0]):
            raise ToolError(f"{not_found[1]}: {exc}") from exc
        raise ToolError(str(exc)) from exc
```

**Why:** The agent receives a structured `{"ok": false, ...}` payload it can report honestly, rather than crashing or exposing internal errors.

### Structured output schemas

Output types live in `mcp/schemas.py` and compose domain schemas:

```python
class AccountTransactionsOutput(BaseModel):
    account_id: str
    transaction_count: int
    returned: int
    transactions: list[TransactionSummary]
```

**Why separate from domain schemas?** MCP output shapes may differ from REST response shapes. The MCP layer controls exactly what fields reach the agent — a form of data minimization.

---

## 8. How the LLM, MCP, and AGENTS.md Work Together

This is the heart of the agent path. Three components play distinct roles:

| Component | Role |
|-----------|------|
| **Gemini** | Reasons about the user question; selects which tool to call |
| **MCP Client** | Executes `tools/list` and `tools/call`; returns structured results |
| **AGENTS.md invariant** | Ensures the code connecting them never bypasses MCP |

### Step 1: Discover tools

On the first request, the agent fetches the MCP tool catalog:

```python
# agent/agent.py
listed = await self._gateway.list_tools()
self._tools = to_llm_tools(listed.tools)
```

MCP tool definitions convert to Gemini function-calling metadata:

```python
# agent/llm.py
def to_llm_tools(tools):
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or tool.title,
                "parameters": tool.input_schema or {"type": "object", "properties": {}},
            },
        }
        for tool in tools
    ]
```

**Why convert formats?** MCP and Gemini use different wire formats. The conversion layer (`llm.py`) is the only place that needs to know both — keeping the agent loop clean.

### Step 2: Tool-selection loop

Gemini returns a tool call; the MCP client executes it:

```python
# agent/agent.py
for _ in range(config.AGENT_MAX_TOOL_ROUNDS):
    completion = await self._llm.complete(messages, tools=tools)
    assistant = completion.choices[0].message
    if not assistant.tool_calls:
        return (assistant.content or "").strip()

    for call in assistant.tool_calls:
        args = json.loads(call.function.arguments or "{}")
        result = await self._gateway.call_tool(name, args)
        messages.append({
            "role": "tool",
            "tool_call_id": call.id,
            "name": name,
            "content": tool_result_payload(result),
        })
```

**Why cap rounds?** `AGENT_MAX_TOOL_ROUNDS` (default 8) prevents runaway tool loops from burning API quota or latency.

### Step 3: Structured results back to the model

```python
# agent/llm.py
def tool_result_payload(result: CallToolResult) -> str:
    if result.structured_content is not None:
        payload = {"ok": not result.is_error, "data": result.structured_content}
    else:
        text = "\n".join(block.text for block in result.content if ...)
        payload = {"ok": not result.is_error, "message": text}
    return json.dumps(payload)
```

**Why wrap in `{"ok": ..., "data": ...}`?** Gives Gemini a consistent envelope whether the tool succeeded, returned not-found, or failed — so it can report honestly instead of guessing.

### Worked example

**User:** `What is the balance for acc-1?`

```text
1. validate_input()          → pass
2. tools/list                → discovers get_account_balance
3. Gemini selects            → get_account_balance(account_id="acc-1")
4. MCP client calls tool     → structured JSON returned
5. Gemini composes reply     → "Account acc-1 (Operating, USD) has a balance of USD 1,250,000.00."
```

**User:** `Transfer USD 500 from acc-1 to acc-2.`

```text
1. validate_input()          → pass
2. Gemini reads system prompt → no write tools exist
3. Gemini declines           → "I only perform read-only lookups and cannot move funds."
```

The system prompt (`agent/prompts.py`) guides this behavior. `AGENTS.md` ensures no write tool exists to call. Code enforces what prompts merely suggest.

---

## 9. Security and Agent Guardrails

Security in this demo operates at three layers. **Prompts alone are not a security boundary** — a principle stated in both `AGENTS.md` and `MCP_SECURITY.md`.

### Layer 1: Input guardrails (code)

Before Gemini sees the message:

```python
# agent/schema.py
MAX_MESSAGE_CHARS = 4000
MAX_HISTORY = 50

_UNSAFE_INPUT = (
    re.compile(r"(?i)\b(ignore|forget|disregard)\b.{0,40}\b(instruction|prompt|rule)s?\b"),
    re.compile(r"(?i)\b(reveal|show|print|dump)\b.{0,30}\b(system prompt|api key|secret|password)\b"),
)

def validate_input(message: str) -> ChatResponse | None:
    if any(pattern.search(text) for pattern in _UNSAFE_INPUT):
        return ChatResponse(status="blocked", reply="I cannot override instructions...")
    return None
```

**Why regex patterns?** Lightweight prompt-injection blocking for a demo. Production systems would add classifier models, rate limits, and auth — noted as future work in `MCP_SECURITY.md`.

### Layer 2: MCP boundary (architecture)

- Read-only tools only
- Structured outputs with explicit schemas
- Agent code imports only `client.py`, never domain services or `db.py`
- Verified statically:

```bash
uv run python mcp_guard.py . --fail-on high
```

**Why static scanning?** Architectural invariants erode over time as contributors add features. `mcp_guard.py` catches bypass paths before they reach production.

### Layer 3: Behavioral guardrails (prompt + loop limits)

The system prompt instructs the model to:

- Call tools before stating any financial fact
- Never invent balances or transaction data
- Decline write operations and off-topic requests
- Report tool failures honestly

Combined with `AGENT_MAX_TOOL_ROUNDS=8` in `.env`:

```bash
# .env.example
AGENT_MAX_TOOL_ROUNDS=8
```

### What this demo does not include

This is a reference implementation, not production banking:

- No authentication on MCP or chat endpoints
- No TLS
- No rate limiting
- No structured audit logging

These are documented as hardening priorities in `MCP_SECURITY.md`.

---

## 10. Running the Demo

### Prerequisites

- Docker (or Python 3.14+ with [uv](https://docs.astral.sh/uv/))
- A Gemini API key for the chat interface

### Option A: Docker Compose (recommended)

```bash
git clone https://github.com/habeneyasu/financial-mcp-gateway.git
cd financial-mcp-gateway
cp .env.example .env
# Edit .env — set GEMINI_API_KEY

docker compose up --build
```

| Service | URL |
|---------|-----|
| MCP | http://127.0.0.1:8000/mcp |
| Chat | http://127.0.0.1:8001/ |
| REST | http://127.0.0.1:8080/docs |

Stop with `docker compose down`. SQLite data persists in the `gateway-data` volume.

> **Note:** If `docker compose` fails under `sudo`, your Compose plugin may be installed for your user only. Run without `sudo`, or use `docker-compose up --build` (hyphenated).

### Option B: Local development

```bash
uv sync
cp .env.example .env

# Terminal 1 — MCP server
uv run python server.py

# Terminal 2 — chat UI
uv run python chat_app.py

# Optional — REST API
uv run uvicorn financial_mcp_gateway.api.router:app --host 0.0.0.0 --port 8080
```

### Direct MCP client (no Gemini)

```python
import asyncio
from client import connect

async def main():
    async with connect() as gateway:
        result = await gateway.call_tool(
            "get_account_balance", {"account_id": "acc-1"}
        )
        print(result.structured_content)

asyncio.run(main())
```

### Chat API

```bash
curl -s -X POST http://127.0.0.1:8001/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"What is the balance for acc-1?"}'
```

### Example prompts to try

| Prompt | Expected tool |
|--------|---------------|
| `What is the balance for acc-1?` | `get_account_balance` |
| `Show recent transactions for acc-1.` | `get_transactions` |
| `How many transactions are in the system?` | `get_transaction_summary` |
| `Transfer USD 500 from acc-1 to acc-2.` | Declined (read-only) |

### Demo data

| Resource | Example IDs |
|----------|-------------|
| Customers | `cust-1` … `cust-5` |
| Accounts | `acc-1`, `acc-2`, `acc-empty` |
| Transactions | `txn_ok_001`, `txn_pending_001`, `txn_fail_nsf_001` |
| Users | `user-1`, … |

---

## 11. Project Structure

```text
server.py              MCP server entry point (Streamable HTTP)
client.py              MCP client (protocol 2026-07-28)
chat_app.py            Gradio chat + POST /chat
mcp_guard.py           Static MCP security scanner
db.py                  SQLite schema, seed data, persistence
AGENTS.md              Rules for AI coding agents editing this repo

src/financial_mcp_gateway/
  agent/
    agent.py             Tool loop orchestration
    llm.py               Gemini integration + MCP ↔ LLM wire format
    prompts.py           System prompt (behavioral guidance)
    schema.py            Input/output guardrails (enforced in code)
  mcp/
    __init__.py          Tool registration
    accounts.py          Account MCP tools
    transactions.py      Transaction MCP tools
    customers.py         Customer MCP tools
    users.py             User MCP tools
    schemas.py           Structured output models
    helpers.py           ToolError mapping, amount formatting
  accounts/              Account domain service
  customers/             Customer domain service
  transactions/          Transaction domain service
  users/                 User domain service
  api/router.py          REST API (parallel interface)
```

### Where to change what

| Change | Location |
|--------|----------|
| New financial capability | Domain service → MCP tool |
| Hard input/output limits | `agent/schema.py` |
| Reply behavior and examples | `agent/prompts.py` |
| Tool orchestration | `agent/agent.py` |
| Gemini wire format | `agent/llm.py` |
| Tool-call round limit | `AGENT_MAX_TOOL_ROUNDS` in `.env` |
| MCP security rules | `mcp_guard.py`, `MCP_SECURITY.md` |
| Coding agent rules | `AGENTS.md` |

### Adding a new capability

Always follow this direction:

```text
Domain Service → MCP Tool → tools/list → Agent discovers → tools/call
```

Never expose domain services directly to the agent layer.

---

## 12. Challenges and Lessons Learned

### Challenge 1: Keeping the MCP boundary intact

**Problem:** It is tempting to import `AccountService` directly in the agent for speed during development.

**Solution:** Codify the invariant in `AGENTS.md`, enforce it with `mcp_guard.py`, and keep the agent loop limited to `GatewayMCPClient` methods.

**Lesson:** Architectural rules written only in READMEs erode. Put them in `AGENTS.md` where coding agents read them, and scan for violations in CI.

### Challenge 2: Wire format translation

**Problem:** MCP tool schemas and Gemini function-calling use different formats.

**Solution:** A dedicated conversion layer in `agent/llm.py` — `to_llm_tools()`, `tool_result_payload()`, `_to_gemini_contents()`.

**Lesson:** Isolate integration glue in one module. The agent loop should not know about Gemini's `FunctionResponse` or MCP's `CallToolResult` internals.

### Challenge 3: Structured vs. unstructured tool output

**Problem:** Text tool results force the model to parse strings, increasing hallucination risk.

**Solution:** Every tool uses `structured_output=True` with Pydantic return types. Results flow to Gemini as JSON via `result.structured_content`.

**Lesson:** Structured outputs are worth the upfront schema work. They pay off in reliability and testability.

### Challenge 4: Prompt injection in a financial context

**Problem:** Users may attempt to override instructions or exfiltrate secrets.

**Solution:** Regex-based input blocking in code (not prompts), plus a system prompt that declines write operations.

**Lesson:** Defense in depth — prompts guide behavior; code blocks known attack patterns; MCP limits what tools can do regardless of prompt content.

### Challenge 5: Docker Compose plugin paths

**Problem:** `sudo docker compose` fails when the Compose plugin is installed only in the user's home directory.

**Solution:** Run `docker compose` without sudo, or use the standalone `docker-compose` binary.

**Lesson:** Dev environment docs should mention common Docker permission and plugin path issues.

---

## 13. What I Learned About Building Agentic Systems

1. **Separate tool selection from tool invocation.** The LLM decides *what* to call; the MCP client *executes* the call. This split makes the boundary auditable and testable.

2. **MCP is a capability layer, not a database adapter.** Tools should be narrow, purpose-specific, and typed — not generic "run SQL" or "call any API" functions.

3. **Structured outputs change agent reliability.** When Gemini receives `{"ok": true, "data": {"balance": "1250000.00", ...}}`, it composes accurate replies. When it receives unstructured text, parsing errors and hallucinations increase.

4. **Prompts guide; code enforces.** A system prompt saying "never invent balances" helps. A read-only tool catalog with no write tools *guarantees* it.

5. **AGENTS.md is infrastructure.** As AI coding agents become part of the development workflow, repository-level rules files (`AGENTS.md`) are as important as linters for preserving architectural intent.

6. **Start read-only, grow deliberately.** Mutation tools need idempotency, auth, audit logging, and adversarial testing. A read-only demo teaches the MCP boundary without opening write-path security holes.

---

## 14. Future Extensions

This demo is intentionally scoped. Natural next steps:

| Extension | Why | Where to start |
|-----------|-----|----------------|
| **OAuth on MCP transport** | Authenticate callers before `tools/call` | `config.py` OAuth settings; MCP server middleware |
| **Structured audit logging** | Record tool name, caller, target ID, outcome | MCP tool handlers; `mcp_guard.py` already flags missing audit logs |
| **Rate limiting** | Prevent abuse of MCP and chat endpoints | `chat_app.py`, MCP server middleware |
| **Write tools with idempotency** | Transfers, payments — with explicit security design | Domain service → MCP tool, following `idempotency/` module pattern |
| **Multi-tenant isolation** | Separate customer data by tenant | Domain services + MCP tool scoping |
| **Additional MCP capabilities** | Resources, prompts, sampling | MCP server registration alongside existing tools |

Each extension must preserve the core invariant from `AGENTS.md`:

```text
AI Agent → MCP → Financial Capabilities → Domain Services → Data
```

---

## 15. Conclusion

Building this Financial MCP Gateway on **MCP 2026-07-28** taught me that the protocol release is not just a transport upgrade — it is a foundation for **trustworthy agent integration** over sensitive data.

The combination that makes this work:

- **MCP 2026-07-28** — Streamable HTTP, structured tool I/O, protocol-aware SDK
- **Layered architecture** — agent, MCP client, MCP server, domain services, database
- **AGENTS.md** — development-time rules that preserve the runtime MCP boundary
- **Code-level guardrails** — input validation, loop limits, static security scanning
- **Read-only, narrow tools** — the agent gets capabilities, not system access

The demo repository is open for cloning, extension, and learning:

**[github.com/habeneyasu/financial-mcp-gateway](https://github.com/habeneyasu/financial-mcp-gateway)**

If you are building agent integrations over financial or regulated data, start with explicit MCP capabilities — narrow, typed, and read-only — and grow from there with deliberate security design at every step.

---

*This article supports the AAIF Ambassadors MCP 2026-07-28 Education Campaign — contributing a blog-style migration diary and a runnable demo repository for the community.*
