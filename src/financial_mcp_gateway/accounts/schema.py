"""Account request and response schemas."""

from pydantic import BaseModel, Field, field_validator

_ALLOWED_STATUSES = {"open", "closed"}
_ALLOWED_ACCOUNT_TYPES = {
    "operating",
    "reserve",
    "treasury",
    "payroll",
    "collections",
    "petty_cash",
    "checking",
    "savings",
}


class AccountCreate(BaseModel):
    customer_id: str = Field(min_length=1, max_length=64)
    account_number: str = Field(min_length=1, max_length=32)
    account_type: str = Field(min_length=1, max_length=32)
    currency: str = Field(min_length=3, max_length=3)
    balance_cents: int = Field(default=0, ge=0)
    status: str = "open"

    @field_validator(
        "customer_id",
        "account_number",
        "account_type",
        "currency",
        "status",
        mode="before",
    )
    @classmethod
    def strip_required(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("account_type")
    @classmethod
    def account_type_allowed(cls, value: str) -> str:
        normalized = value.lower().replace("-", "_").replace(" ", "_")
        if normalized not in _ALLOWED_ACCOUNT_TYPES:
            allowed = ", ".join(sorted(_ALLOWED_ACCOUNT_TYPES))
            raise ValueError(f"account_type must be one of: {allowed}")
        return normalized

    @field_validator("currency")
    @classmethod
    def currency_upper(cls, value: str) -> str:
        return value.upper()

    @field_validator("status")
    @classmethod
    def status_allowed(cls, value: str) -> str:
        if value not in _ALLOWED_STATUSES:
            raise ValueError("status must be open or closed")
        return value


class AccountResponse(BaseModel):
    id: str
    customer_id: str
    account_number: str
    account_type: str
    currency: str
    balance_cents: int
    status: str
    created_at: str
