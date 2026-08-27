"""Idempotency-key request and response schemas."""

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class IdempotencyStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class IdempotencyKeyCreate(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    key: str = Field(min_length=1, max_length=128)
    request_hash: str = Field(min_length=1, max_length=128)
    status: IdempotencyStatus = IdempotencyStatus.PENDING
    http_status: int | None = Field(default=None, ge=100, le=599)
    response_body: str | None = None

    @field_validator("user_id", "key", "request_hash", mode="before")
    @classmethod
    def strip_required(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("response_body", mode="before")
    @classmethod
    def strip_optional(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class IdempotencyKeyResponse(BaseModel):
    user_id: str
    key: str
    request_hash: str
    status: IdempotencyStatus
    http_status: int | None = None
    response_body: str | None = None
    created_at: str
    expires_at: str


class IdempotencyKeyListResponse(BaseModel):
    total: int
    returned: int
    keys: list[IdempotencyKeyResponse]
