"""MCP tools for idempotency keys."""

from __future__ import annotations

from typing import TYPE_CHECKING

from financial_mcp_gateway.idempotency.schema import IdempotencyKeyResponse
from financial_mcp_gateway.idempotency.service import IdempotencyKeyNotFound, IdempotencyService
from financial_mcp_gateway.mcp.helpers import run_tool

if TYPE_CHECKING:
    from mcp.server import MCPServer


def register_idempotency_tools(mcp: MCPServer) -> None:
    service = IdempotencyService()

    @mcp.tool(
        title="Get idempotency key",
        description="Return an idempotency key for a user and key pair.",
        structured_output=True,
    )
    async def get_idempotency_key(user_id: str, key: str) -> IdempotencyKeyResponse:
        def _run() -> IdempotencyKeyResponse:
            return service.get_key(user_id, key)

        return run_tool(
            _run,
            not_found=(IdempotencyKeyNotFound, "idempotency_key_not_found"),
        )
