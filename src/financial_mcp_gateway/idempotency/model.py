"""Idempotency-key persistence models."""

from pydantic import BaseModel

from financial_mcp_gateway.idempotency.schema import IdempotencyStatus


class IdempotencyKey(BaseModel):
    user_id: str
    key: str
    request_hash: str
    status: IdempotencyStatus
    http_status: int | None = None
    response_body: str | None = None
    created_at: str
    expires_at: str
