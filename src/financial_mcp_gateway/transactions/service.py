"""Transaction business logic."""

from __future__ import annotations

import sqlite3
from decimal import Decimal

from db import get_account, get_transaction_by_reference, insert_transaction
from db import list_transactions as db_list_transactions
from financial_mcp_gateway.transactions.schema import (
    TransactionCreate,
    TransactionListResponse,
    TransactionResponse,
)


class TransactionError(Exception):
    """Base error for transaction operations."""


class TransactionNotFound(TransactionError):
    def __init__(self, reference: str) -> None:
        self.reference = reference
        super().__init__(f"transaction not found: {reference}")


class DuplicateTransactionReference(TransactionError):
    def __init__(self, reference: str) -> None:
        self.reference = reference
        super().__init__(f"transaction reference already exists: {reference}")


class TransactionAccountNotFound(TransactionError):
    def __init__(self, account_id: str) -> None:
        self.account_id = account_id
        super().__init__(f"account not found: {account_id}")


class InvalidTransactionReference(TransactionError):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


def _amount_to_db(amount: Decimal) -> int:
    cents = int(amount * 100)
    if cents <= 0:
        raise ValueError("amount must be greater than zero")
    return cents


class TransactionService:
    def create_transaction(self, payload: TransactionCreate) -> TransactionResponse:
        source = get_account(payload.source_account_id)
        if source is None:
            raise TransactionAccountNotFound(payload.source_account_id)

        destination = get_account(payload.destination_account_id)
        if destination is None:
            raise TransactionAccountNotFound(payload.destination_account_id)

        if payload.currency != source["currency"]:
            raise InvalidTransactionReference(
                f"currency must match source account currency: {source['currency']}"
            )

        try:
            row = insert_transaction(
                reference=payload.reference,
                source_account_id=payload.source_account_id,
                destination_account_id=payload.destination_account_id,
                amount=_amount_to_db(payload.amount),
                currency=payload.currency,
                transaction_type=payload.transaction_type.value,
                description=payload.description,
                status="pending",
            )
        except sqlite3.IntegrityError as exc:
            message = str(exc).lower()
            if "reference" in message:
                raise DuplicateTransactionReference(payload.reference) from exc
            raise InvalidTransactionReference(
                "invalid account reference or transaction data"
            ) from exc

        return TransactionResponse.model_validate(row)

    def get_transaction(self, reference: str) -> TransactionResponse:
        reference = reference.strip()
        if not reference:
            raise TransactionNotFound(reference)
        row = get_transaction_by_reference(reference)
        if row is None:
            raise TransactionNotFound(reference)
        return TransactionResponse.model_validate(row)

    def list_transactions(
        self,
        *,
        account_id: str | None = None,
        limit: int = 10,
    ) -> TransactionListResponse:
        if account_id is not None:
            account_id = account_id.strip()
            if not account_id:
                raise TransactionAccountNotFound(account_id)
            if get_account(account_id) is None:
                raise TransactionAccountNotFound(account_id)

        total, rows = db_list_transactions(account_id, limit)
        return TransactionListResponse(
            total=total,
            returned=len(rows),
            transactions=[TransactionResponse.model_validate(row) for row in rows],
        )

    def list_account_transaction_rows(
        self,
        account_id: str,
        limit: int = 10,
    ) -> tuple[int, list[dict]]:
        account_id = account_id.strip()
        if not account_id:
            raise TransactionAccountNotFound(account_id)
        if get_account(account_id) is None:
            raise TransactionAccountNotFound(account_id)
        return db_list_transactions(account_id, limit)
