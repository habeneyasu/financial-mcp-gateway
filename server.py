"""MCP server entry point for the financial gateway."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from mcp.server import MCPServer

from config import MCP_MODERN_PROTOCOL_VERSION, config
from db import init_db
from financial_mcp_gateway.mcp import register_tools

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_server: MCPServer):
    init_db()
    logger.info("database initialized")
    yield


mcp = MCPServer(
    name="financial-mcp-gateway",
    title="Financial MCP Gateway",
    instructions=(
        "Tools for querying customers, accounts, transactions, users, "
        "and idempotency keys in the financial gateway."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

register_tools(mcp)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info(
        "starting MCP server protocol=%s transport=streamable-http "
        "host=0.0.0.0 port=%s path=%s",
        MCP_MODERN_PROTOCOL_VERSION,
        config.PORT,
        config.MCP_PATH,
    )
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=config.PORT,
        streamable_http_path=config.MCP_PATH,
        stateless_http=True,
        json_response=True,
    )


if __name__ == "__main__":
    main()
