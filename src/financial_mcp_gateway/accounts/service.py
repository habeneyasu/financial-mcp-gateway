"""Account business logic."""

from __future__ import annotations

import sqlite3
import uuid

from db import get_account, insert_account
from financial_mcp_gateway.accounts.schema import AccountCreate, AccountResponse


class AccountError(Exception):
    """Base error for account operations."""


class AccountNotFound(AccountError):
    def __init__(self, account_id: str) -> None:
        self.account_id = account_id
        super().__init__(f"Account not found: {account_id}")


class DuplicateAccountNumber(AccountError):
    def __init__(self, account_number: str) -> None:
        self.account_number = account_number
        super().__init__(f"Account number already exists: {account_number}")


class InvalidAccountReference(AccountError):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


def _display_name(account_type: str) -> str:
    return account_type.replace("_", " ").title()


class AccountService:

    def create_account(self, payload: AccountCreate) -> AccountResponse:

        account_id = f"acc-{uuid.uuid4().hex[:12]}"

        try:
            row = insert_account(
                account_id=account_id,
                customer_id=payload.customer_id,
                account_number=payload.account_number,
                account_type=payload.account_type,
                name=_display_name(payload.account_type),
                currency=payload.currency,
                balance_cents=payload.balance_cents,
                status=payload.status,
            )
        except sqlite3.IntegrityError as exc:
            message = str(exc).lower()
            if "account_number" in message:
                raise DuplicateAccountNumber(payload.account_number) from exc
            raise InvalidAccountReference(
                "Invalid customer_id or account reference"
            ) from exc
        return AccountResponse.model_validate(row)

    def get_account(self, account_id: str) -> AccountResponse:
        account_id = account_id.strip()
        if not account_id:
            raise AccountNotFound(account_id)
        row = get_account(account_id)
        if row is None:
            raise AccountNotFound(account_id)
        return AccountResponse.model_validate(row)

    def get_account_balance_details(self, account_id: str) -> dict:
        """Return enriched account row for MCP balance tools."""
        account_id = account_id.strip()
        if not account_id:
            raise AccountNotFound(account_id)
        row = get_account(account_id)
        if row is None:
            raise AccountNotFound(account_id)
        return row


