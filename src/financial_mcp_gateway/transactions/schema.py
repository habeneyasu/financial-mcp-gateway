"""Transaction request and response schemas."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator

_ALLOWED_CURRENCIES_MIN_LEN = 3


class TransactionType(str, Enum):
    TRANSFER = "transfer"
    PAYMENT = "payment"
    PAYOUT = "payout"


class TransactionStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERSED = "reversed"


def _amount_from_db(value: object) -> object:
    if isinstance(value, int):
        return Decimal(value) / 100
    return value


class TransactionCreate(BaseModel):
    reference: str = Field(min_length=1, max_length=100)
    source_account_id: str = Field(min_length=1, max_length=64)
    destination_account_id: str = Field(min_length=1, max_length=64)
    amount: Decimal = Field(gt=0, decimal_places=2)
    currency: str = Field(min_length=_ALLOWED_CURRENCIES_MIN_LEN, max_length=3)
    description: str = Field(min_length=1, max_length=255)
    transaction_type: TransactionType = TransactionType.TRANSFER

    @field_validator(
        "reference",
        "source_account_id",
        "destination_account_id",
        "currency",
        "description",
        mode="before",
    )
    @classmethod
    def strip_required(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("currency")
    @classmethod
    def currency_upper(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def validate_accounts(self) -> TransactionCreate:
        if self.source_account_id == self.destination_account_id:
            raise ValueError("source and destination accounts must be different")
        return self


class TransactionResponse(BaseModel):
    id: int
    reference: str
    source_account_id: str
    destination_account_id: str
    amount: Decimal = Field(gt=0, decimal_places=2)
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


class TransactionListResponse(BaseModel):
    total: int
    returned: int
    transactions: list[TransactionResponse]


class TransactionSummaryResponse(BaseModel):
    transaction_count: int
    by_status: dict[str, int]
