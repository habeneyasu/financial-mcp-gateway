"""MCP tools for users."""

from __future__ import annotations

from typing import TYPE_CHECKING

from financial_mcp_gateway.mcp.helpers import run_tool
from financial_mcp_gateway.users.schema import UserListResponse, UserResponse
from financial_mcp_gateway.users.service import UserNotFound, UserService

if TYPE_CHECKING:
    from mcp.server import MCPServer


def register_user_tools(mcp: MCPServer) -> None:
    service = UserService()

    @mcp.tool(
        title="Get user",
        description="Return user details by user ID.",
        structured_output=True,
    )
    async def get_user(user_id: str) -> UserResponse:
        def _run() -> UserResponse:
            return service.get_user(user_id)

        return run_tool(_run, not_found=(UserNotFound, "user_not_found"))

    @mcp.tool(
        title="List users",
        description="List users, optionally filtered by customer ID.",
        structured_output=True,
    )
    async def list_users(customer_id: str | None = None, limit: int = 100) -> UserListResponse:
        def _run() -> UserListResponse:
            return service.list_users(customer_id=customer_id, limit=limit)

        return run_tool(_run)
