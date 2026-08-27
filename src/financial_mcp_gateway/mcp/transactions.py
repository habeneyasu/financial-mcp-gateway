"""MCP tools for transactions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from financial_mcp_gateway.mcp.helpers import format_amount, run_tool
from financial_mcp_gateway.mcp.schemas import (
    AccountTransactionsOutput,
    TransactionAccountRef,
    TransactionSummary,
)
from financial_mcp_gateway.transactions.schema import TransactionResponse
from financial_mcp_gateway.transactions.service import (
    TransactionAccountNotFound,
    TransactionNotFound,
    TransactionService,
)

if TYPE_CHECKING:
    from mcp.server import MCPServer


def register_transaction_tools(mcp: MCPServer) -> None:
    service = TransactionService()

    @mcp.tool(
        title="List account transactions",
        description="Return recent transactions for an account.",
        structured_output=True,
    )
    async def get_transactions(account_id: str, limit: int = 10) -> AccountTransactionsOutput:
        def _run() -> AccountTransactionsOutput:
            total, rows = service.list_account_transaction_rows(account_id, limit)
            return AccountTransactionsOutput(
                account_id=account_id,
                transaction_count=total,
                returned=len(rows),
                transactions=[
                    TransactionSummary(
                        id=row["id"],
                        reference=row["reference"],
                        status=row["status"],
                        failure_code=row["failure_code"],
                        type=row["type"],
                        direction=row["direction"],
                        amount=format_amount(row["amount"]),
                        currency=row["currency"],
                        source_account=TransactionAccountRef(
                            id=row["source_account_id"],
                            name=row["source_account_name"],
                            currency=row["source_currency"],
                        ),
                        destination_account=TransactionAccountRef(
                            id=row["destination_account_id"],
                            name=row["destination_account_name"],
                            currency=row["destination_currency"],
                        ),
                        description=row["description"],
                        created_at=row["created_at"],
                    )
                    for row in rows
                ],
            )

        return run_tool(
            _run,
            not_found=(TransactionAccountNotFound, "account_not_found"),
        )

    @mcp.tool(
        title="Get transaction",
        description="Return a transaction by its reference.",
        structured_output=True,
    )
    async def get_transaction(reference: str) -> TransactionResponse:
        def _run() -> TransactionResponse:
            return service.get_transaction(reference)

        return run_tool(_run, not_found=(TransactionNotFound, "transaction_not_found"))
