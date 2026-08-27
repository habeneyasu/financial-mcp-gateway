"""Transaction persistence models."""

from decimal import Decimal

from pydantic import AliasChoices, BaseModel, Field, model_validator

from financial_mcp_gateway.transactions.schema import (
    TransactionStatus,
    TransactionType,
    _amount_from_db,
)


class Transaction(BaseModel):
    id: int
    reference: str
    source_account_id: str
    destination_account_id: str
    amount: Decimal
    currency: str
    description: str
    transaction_type: TransactionType = Field(validation_alias=AliasChoices("type", "transaction_type"))
    status: TransactionStatus
    failure_code: str | None = None
    created_at: str

    @model_validator(mode="before")
    @classmethod
    def normalize_row(cls, data: object) -> object:
        if isinstance(data, dict):
            row = dict(data)
            if isinstance(row.get("amount"), int):
                row["amount"] = _amount_from_db(row["amount"])
            return row
        return data
