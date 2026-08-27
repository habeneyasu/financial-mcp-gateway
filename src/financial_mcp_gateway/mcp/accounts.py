"""MCP tools for accounts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from financial_mcp_gateway.accounts.schema import AccountResponse
from financial_mcp_gateway.accounts.service import AccountNotFound, AccountService
from financial_mcp_gateway.mcp.helpers import format_amount, run_tool
from financial_mcp_gateway.mcp.schemas import AccountBalanceCustomer, AccountBalanceOutput

if TYPE_CHECKING:
    from mcp.server import MCPServer


def register_account_tools(mcp: MCPServer) -> None:
    service = AccountService()

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
                account_number=account["account_number"],
                account_type=account["account_type"],
                name=account["name"],
                currency=account["currency"],
                status=account["status"],
                balance=format_amount(account["balance_cents"]),
                transaction_count=account["transaction_count"],
            )

        return run_tool(_run, not_found=(AccountNotFound, "account_not_found"))

    @mcp.tool(
        title="Get account",
        description="Return account details by account ID.",
        structured_output=True,
    )
    async def get_account(account_id: str) -> AccountResponse:
        def _run() -> AccountResponse:
            return service.get_account(account_id)

        return run_tool(_run, not_found=(AccountNotFound, "account_not_found"))
