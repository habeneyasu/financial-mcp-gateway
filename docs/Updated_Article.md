# Building a Financial MCP Gateway with MCP 2026-07-28

**A practical MCP 2026-07-28 demo, architecture walkthrough, and reference implementation for the AAIF Ambassadors MCP Education Campaign**

**Repository:** `github.com/habeneyasu/financial-mcp-gateway`

---

## 1. Why This Project?

I built this project as part of the **AAIF Ambassadors MCP 2026-07-28 Education Campaign** to explore the latest MCP specification through a practical financial use case.

Rather than explaining MCP only through concepts, I wanted to build a small system where the changes in the new specification could be seen in a working implementation.

The project focuses on three things:

1. **MCP 2026-07-28** and the capabilities it provides for modern agent integrations.
2. **AGENTS.md** as a way to preserve architectural rules during AI-assisted development.
3. **A clear, runnable architecture** showing how the LLM, MCP client, MCP server, application services, and data layer work together.

The goal is not to build a production banking platform. It is to provide a simple environment where developers can **run the project, inspect the implementation, call MCP tools, and understand the architecture**.

---

## 2. What Problem Does It Solve?

Financial systems contain sensitive information, so giving an AI agent broad access to the underlying system is not a good design.

For example, if a user asks:

> "What is the balance of account acc-1?"

The agent needs access to the correct financial data, but it should not need direct access to:

* the database,
* internal business services,
* unrestricted REST APIs, or
* write operations such as transfers.

This project addresses that problem by making **MCP the capability boundary** between the agent and the financial system.

The agent does not directly access the financial domain.

Instead:

```text
User
  ↓
LLM / Agent
  ↓
MCP Client
  ↓
MCP Server
  ↓
MCP Tool
  ↓
Domain Service
  ↓
SQLite
```

This means the agent receives only the capabilities explicitly exposed through MCP.

For this prototype, those capabilities are intentionally **narrow and read-only**.

---

## 3. Why MCP 2026-07-28?

The main reason for building this project was to work with the **MCP 2026-07-28 specification**, rather than simply reproducing an older MCP implementation.

The implementation focuses particularly on:

### Streamable HTTP

The MCP server uses Streamable HTTP:

```python
mcp.run(
    transport="streamable-http",
    host="0.0.0.0",
    port=config.PORT,
    streamable_http_path=config.MCP_PATH,
    stateless_http=True,
    json_response=True,
)
```

This gives the prototype a straightforward HTTP-based MCP endpoint:

```text
/mcp
```

It also makes the service easy to run inside Docker and test using standard HTTP-based infrastructure.

### Structured tool outputs

The financial tools return structured Pydantic models instead of relying only on free-form text.

For example:

```python
@mcp.tool(
    title="Get account balance",
    description="Return balance and metadata for a financial account.",
    structured_output=True,
)
async def get_account_balance(account_id: str) -> AccountBalanceOutput:
    ...
```

The result can therefore be represented as structured data:

```json
{
  "account_id": "acc-1",
  "currency": "USD",
  "balance": "1250000.00",
  "transaction_count": 3
}
```

This makes the interface easier for an agent to consume, validate, test, and reason about.

### Explicit protocol version

The client explicitly targets:

```text
2026-07-28
```

The purpose is to make the implementation clearly aligned with the target specification rather than depending on implicit or mixed protocol behavior.

The important point is that **the project is not a migration of an existing application**. It was implemented directly against the MCP 2026-07-28 version to explore how the specification can be applied in a realistic prototype.

---

## 4. MCP and AGENTS.md Solve Different Problems

One of the interesting parts of this project is the combination of **MCP** and **AGENTS.md**.

They operate at different stages.

**MCP controls the runtime capability boundary.**

It defines what the financial agent can discover and call.

**AGENTS.md controls development-time behavior.**

It provides instructions for AI coding agents working on the repository so that they do not accidentally break the architecture.

For example, the repository establishes a rule that code in the agent layer must not directly import domain services or the database.

The intended direction is:

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

Instead of allowing:

```text
Agent
  ↓
Domain Service
  ↓
Database
```

This is important because architectural boundaries can easily be weakened when AI coding agents modify a project.

`AGENTS.md` makes the architectural intention explicit, while `mcp_guard.py` provides an additional static check for violations.

In simple terms:

> **MCP protects the runtime boundary; AGENTS.md helps protect the architecture during development.**

---

## 5. Overall Architecture

The project contains several components, but each has a clear responsibility.

```text
                         ┌─────────────────┐
                         │      User       │
                         └────────┬────────┘
                                  ↓
                         ┌─────────────────┐
                         │   Gemini / LLM  │
                         │  Agent Layer    │
                         └────────┬────────┘
                                  ↓
                         ┌─────────────────┐
                         │   MCP Client    │
                         └────────┬────────┘
                                  ↓
                         ┌─────────────────┐
                         │   MCP Server    │
                         │ Streamable HTTP │
                         └────────┬────────┘
                                  ↓
                         ┌─────────────────┐
                         │    MCP Tools   │
                         └────────┬────────┘
                                  ↓
                         ┌─────────────────┐
                         │ Domain Services │
                         └────────┬────────┘
                                  ↓
                         ┌─────────────────┐
                         │     SQLite      │
                         └─────────────────┘

              ┌──────────────────────────────┐
              │          REST API            │
              │     Traditional clients      │
              └──────────────┬───────────────┘
                             ↓
                       Domain Services
```

The important architectural decision is that **the MCP layer and REST API share the domain services, but the agent does not bypass MCP**.

The REST API exists for traditional application integrations.

MCP exists for agent-oriented access.

This keeps the responsibilities separate without duplicating the business logic.

---

## 6. How a Request Works

Consider:

> "What is the balance for acc-1?"

The request follows this path:

```text
1. User sends the question
        ↓
2. Agent validates the input
        ↓
3. Agent discovers available MCP tools
        ↓
4. Gemini selects get_account_balance
        ↓
5. MCP Client calls the MCP Server
        ↓
6. MCP Tool calls the Account domain service
        ↓
7. Domain service reads SQLite
        ↓
8. Structured result returns through MCP
        ↓
9. Gemini generates the response
        ↓
10. User receives the answer
```

The LLM decides **which capability is needed**.

The MCP client is responsible for **calling that capability**.

The domain service is responsible for **business logic and data access**.

This separation makes the flow easier to understand, test, and control.

---

## 7. Why Keep the Prototype Simple?

A major design decision was to avoid unnecessary infrastructure.

The project uses **SQLite with seeded demonstration data**, so there is no need to install or configure an external database just to understand MCP.

The objective is experimentation, not infrastructure management.

A developer can:

```bash
git clone https://github.com/habeneyasu/financial-mcp-gateway.git
cd financial-mcp-gateway
docker compose up --build
```

and start exploring the system.

The project can also be tested through the hosted **Hugging Face demo**, allowing developers to experiment without setting up the project locally.

This makes the prototype useful as an educational reference: **clone it, run it, call the MCP tools, inspect the architecture, and modify it.**

---

## 8. What the MCP Layer Exposes

The MCP server intentionally exposes a small set of read-only financial capabilities.

Examples include:

```text
get_customer
get_account
get_account_balance
get_transactions
get_transaction
get_transaction_summary
get_user
list_users
```

The tools are deliberately narrow.

There is no generic:

```text
execute_sql()
```

or:

```text
call_any_api()
```

tool.

Instead, each capability has a specific purpose and a defined input/output contract.

This demonstrates an important design principle:

> **MCP should expose capabilities, not unrestricted access to the underlying system.**

---

## 9. Guardrails and Architectural Protection

The prototype uses several layers of protection.

### Input guardrails

The agent validates incoming messages and blocks some known prompt-injection patterns.

### MCP boundary

The agent can only use the tools exposed by the MCP server.

### Read-only scope

The current tool catalog does not provide financial mutation operations such as transfers or payments.

### Tool-call limits

The agent has a maximum number of tool rounds to prevent uncontrolled tool loops.

### Static architecture checks

`mcp_guard.py` checks important architectural rules, including the MCP boundary.

### AGENTS.md

`AGENTS.md` communicates these architectural expectations to AI coding agents working on the repository.

These mechanisms are not presented as production-grade financial security. They demonstrate how **protocol boundaries, code-level controls, and development-time rules can work together**.

---

## 10. What I Learned

Building this prototype highlighted several practical lessons.

### MCP is more than a tool-calling interface

The value is not simply calling a function from an LLM. The important part is establishing a clear boundary between an agent and the capabilities it is allowed to use.

### Structured outputs matter

Typed outputs make the contract between the MCP server and agent much clearer than relying entirely on free-form text.

### Architecture should be enforceable

Documentation can describe an architecture, but AI-assisted development makes it increasingly important to encode important architectural rules in `AGENTS.md` and automated checks.

### A good MCP demo does not need a complex infrastructure

Using SQLite, Docker Compose, and seeded data makes it possible to focus on MCP itself rather than spending time configuring supporting infrastructure.

### Read-only is a useful starting point

Financial write operations introduce considerably more complexity around authorization, idempotency, auditing, and security. Starting with read-only capabilities keeps the demonstration focused.

---

## 11. Conclusion

This project is a practical exploration of **MCP 2026-07-28**, rather than a migration of an existing MCP application.

The focus is on showing how the newer MCP specification can be used in a realistic financial scenario while keeping the implementation small enough to understand.

The key ideas are:

* **MCP 2026-07-28** provides the runtime capability interface.
* **Streamable HTTP** provides a simple HTTP-based MCP deployment model.
* **Structured outputs** provide clear contracts between tools and agents.
* **AGENTS.md** helps preserve architectural boundaries during AI-assisted development.
* **Read-only MCP tools** demonstrate controlled access to financial capabilities.
* **SQLite and Docker** keep the prototype simple and reproducible.
* **A clear separation between LLM, MCP, domain services, REST, and data** makes the architecture easy to inspect and extend.

The project is intended as a **learning and reference implementation**: something developers can run, understand, experiment with, and use as a starting point for their own MCP-based systems.

> **The objective is not to make the financial system accessible to the agent. It is to make the right financial capabilities accessible to the agent through an explicit MCP boundary.**

---

**Project:** `github.com/habeneyasu/financial-mcp-gateway`

**Campaign:** AAIF Ambassadors MCP 2026-07-28 Education Campaign
