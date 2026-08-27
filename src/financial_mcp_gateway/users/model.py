"""User persistence models."""

from pydantic import BaseModel


class User(BaseModel):
    id: str
    customer_id: str
    username: str
    email: str
    role: str
    created_at: str
