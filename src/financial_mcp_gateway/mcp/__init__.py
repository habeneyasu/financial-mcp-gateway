"""MCP tool registration for the financial gateway."""

from __future__ import annotations

from typing import TYPE_CHECKING

from financial_mcp_gateway.mcp.accounts import register_account_tools
from financial_mcp_gateway.mcp.customers import register_customer_tools
from financial_mcp_gateway.mcp.idempotency import register_idempotency_tools
from financial_mcp_gateway.mcp.transactions import register_transaction_tools
from financial_mcp_gateway.mcp.users import register_user_tools

if TYPE_CHECKING:
    from mcp.server import MCPServer


def register_tools(mcp: MCPServer) -> None:
    register_customer_tools(mcp)
    register_account_tools(mcp)
    register_transaction_tools(mcp)
    register_user_tools(mcp)
    register_idempotency_tools(mcp)
