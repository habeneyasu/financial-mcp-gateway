"""MCP tools for customers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from financial_mcp_gateway.customers.schema import CustomerResponse
from financial_mcp_gateway.customers.service import CustomerNotFound, CustomerService
from financial_mcp_gateway.mcp.helpers import run_tool

if TYPE_CHECKING:
    from mcp.server import MCPServer


def register_customer_tools(mcp: MCPServer) -> None:
    service = CustomerService()

    @mcp.tool(
        title="Get customer",
        description="Return customer details by customer ID.",
        structured_output=True,
    )
    async def get_customer(customer_id: str) -> CustomerResponse:
        def _run() -> CustomerResponse:
            return service.get_customer(customer_id)

        return run_tool(_run, not_found=(CustomerNotFound, "customer_not_found"))
