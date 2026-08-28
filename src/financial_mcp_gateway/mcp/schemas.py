"""Structured output schemas for MCP tools (2026-07-28)."""

from __future__ import annotations

from pydantic import BaseModel

from financial_mcp_gateway.accounts.schema import AccountResponse
from financial_mcp_gateway.customers.schema import CustomerResponse
from financial_mcp_gateway.idempotency.schema import IdempotencyKeyResponse
from financial_mcp_gateway.transactions.schema import TransactionResponse
from financial_mcp_gateway.users.schema import UserListResponse, UserResponse


class AccountBalanceCustomer(BaseModel):
    id: str
    first_name: str
    last_name: str


class AccountBalanceOutput(BaseModel):
    account_id: str
    customer: AccountBalanceCustomer
    account_number: str
    account_type: str
    name: str
    currency: str
    status: str
    balance: str
    transaction_count: int


class TransactionAccountRef(BaseModel):
    id: str
    name: str
    currency: str


class TransactionSummary(BaseModel):
    id: int
    reference: str
    status: str
    failure_code: str | None
    type: str
    direction: str
    amount: str
    currency: str
    source_account: TransactionAccountRef
    destination_account: TransactionAccountRef
    description: str
    created_at: str


class AccountTransactionsOutput(BaseModel):
    account_id: str
    transaction_count: int
    returned: int
    transactions: list[TransactionSummary]


class SystemTransactionSummaryOutput(BaseModel):
    transaction_count: int
    by_status: dict[str, int]


__all__ = [
    "AccountBalanceOutput",
    "AccountResponse",
    "AccountTransactionsOutput",
    "SystemTransactionSummaryOutput",
    "CustomerResponse",
    "IdempotencyKeyResponse",
    "TransactionResponse",
    "UserListResponse",
    "UserResponse",
]
