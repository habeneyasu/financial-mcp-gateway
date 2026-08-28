"""Hugging Face Spaces entrypoint.

Mounts the MCP Starlette app at /mcp and the Gradio chat UI at /
onto a single FastAPI instance running on port 7860.

The MCP client inside the agent is pointed at http://127.0.0.1:7860/mcp
via MCP_URL so everything runs in one process — no subprocess needed.

Required secret (set in HF Space settings):
  GEMINI_API_KEY
Optional:
  GEMINI_MODEL   (default: gemini-2.5-flash)
"""

from __future__ import annotations

import logging
import os
import sys

# Ensure src/ is importable (mirrors the local dev layout)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Point the MCP client at this same process
os.environ.setdefault("PORT", "7860")
os.environ.setdefault("MCP_URL", "http://127.0.0.1:7860/mcp")
os.environ.setdefault("DATABASE_PATH", "/tmp/gateway.db")
os.environ.setdefault("GEMINI_MODEL", "gemini-2.5-flash")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from contextlib import asynccontextmanager  # noqa: E402

import uvicorn  # noqa: E402
from mcp.server import MCPServer  # noqa: E402

from config import MCP_MODERN_PROTOCOL_VERSION, config  # noqa: E402
from db import init_db  # noqa: E402
from financial_mcp_gateway.mcp import register_tools  # noqa: E402

# ── Build MCP server ──────────────────────────────────────────────────────────

mcp = MCPServer(
    name="financial-mcp-gateway",
    title="Financial MCP Gateway",
    instructions=(
        "Tools for querying customers, accounts, transactions, users, "
        "and idempotency keys in the financial gateway."
    ),
    version="0.1.0",
)
register_tools(mcp)

mcp_starlette = mcp.streamable_http_app(
    streamable_http_path="/mcp",
    stateless_http=True,
    json_response=True,
)

# ── Wrap chat_app with db-init lifespan and mount MCP ────────────────────────

from chat_app import app as _chat_app  # noqa: E402  (import after env vars set)


@asynccontextmanager
async def lifespan(_app):
    init_db()
    logger.info(
        "db initialized | MCP protocol=%s | MCP_URL=%s",
        MCP_MODERN_PROTOCOL_VERSION,
        config.mcp_url,
    )
    yield


_chat_app.router.lifespan_context = lifespan
_chat_app.mount("/mcp", mcp_starlette)

app = _chat_app


def main() -> None:
    logger.info("starting Financial MCP Gateway Space on port 7860")
    uvicorn.run("space_app:app", host="0.0.0.0", port=7860, log_level="info")


if __name__ == "__main__":
    main()
