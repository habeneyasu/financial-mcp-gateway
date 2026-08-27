"""Idempotency-key business logic."""

from __future__ import annotations

import sqlite3

from db import get_idempotency_key, get_user, insert_idempotency_key
from db import list_idempotency_keys as db_list_idempotency_keys
from financial_mcp_gateway.idempotency.schema import (
    IdempotencyKeyCreate,
    IdempotencyKeyListResponse,
    IdempotencyKeyResponse,
)


class IdempotencyError(Exception):
    """Base error for idempotency operations."""


class IdempotencyKeyNotFound(IdempotencyError):
    def __init__(self, user_id: str, key: str) -> None:
        self.user_id = user_id
        self.key = key
        super().__init__(f"idempotency key not found: {user_id}/{key}")


class DuplicateIdempotencyKey(IdempotencyError):
    def __init__(self, user_id: str, key: str) -> None:
        self.user_id = user_id
        self.key = key
        super().__init__(f"idempotency key already exists: {user_id}/{key}")


class InvalidIdempotencyReference(IdempotencyError):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class IdempotencyService:
    def create_key(self, payload: IdempotencyKeyCreate) -> IdempotencyKeyResponse:
        if get_user(payload.user_id) is None:
            raise InvalidIdempotencyReference(f"user not found: {payload.user_id}")

        try:
            row = insert_idempotency_key(
                user_id=payload.user_id,
                key=payload.key,
                request_hash=payload.request_hash,
                status=payload.status.value,
                http_status=payload.http_status,
                response_body=payload.response_body,
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateIdempotencyKey(payload.user_id, payload.key) from exc

        return IdempotencyKeyResponse.model_validate(row)

    def get_key(self, user_id: str, key: str) -> IdempotencyKeyResponse:
        user_id = user_id.strip()
        key = key.strip()
        if not user_id or not key:
            raise IdempotencyKeyNotFound(user_id, key)
        row = get_idempotency_key(user_id, key)
        if row is None:
            raise IdempotencyKeyNotFound(user_id, key)
        return IdempotencyKeyResponse.model_validate(row)

    def list_keys(
        self,
        *,
        user_id: str | None = None,
        limit: int = 100,
    ) -> IdempotencyKeyListResponse:
        if user_id is not None:
            user_id = user_id.strip()
            if not user_id:
                raise InvalidIdempotencyReference("user_id must not be empty")
            if get_user(user_id) is None:
                raise InvalidIdempotencyReference(f"user not found: {user_id}")

        total, rows = db_list_idempotency_keys(user_id, limit)
        return IdempotencyKeyListResponse(
            total=total,
            returned=len(rows),
            keys=[IdempotencyKeyResponse.model_validate(row) for row in rows],
        )
