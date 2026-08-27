"""Account persistence models."""

from pydantic import BaseModel


class Account(BaseModel):
    id: str
    customer_id: str
    account_number: str
    account_type: str
    currency: str
    balance_cents: int
    status: str
    created_at: str
