"""User business logic."""

from __future__ import annotations

import sqlite3
import uuid

from db import get_customer, get_user, hash_password, insert_user
from db import list_users as db_list_users
from financial_mcp_gateway.users.schema import UserCreate, UserListResponse, UserResponse


class UserError(Exception):
    """Base error for user operations."""


class UserNotFound(UserError):
    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        super().__init__(f"user not found: {user_id}")


class DuplicateUserEmail(UserError):
    def __init__(self, email: str) -> None:
        self.email = email
        super().__init__(f"user email already exists: {email}")


class DuplicateUsername(UserError):
    def __init__(self, username: str) -> None:
        self.username = username
        super().__init__(f"username already exists: {username}")


class InvalidUserReference(UserError):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class UserService:
    def create_user(self, payload: UserCreate) -> UserResponse:
        if get_customer(payload.customer_id) is None:
            raise InvalidUserReference(f"customer not found: {payload.customer_id}")

        user_id = f"user-{uuid.uuid4().hex[:12]}"
        try:
            row = insert_user(
                user_id=user_id,
                customer_id=payload.customer_id,
                username=payload.username,
                password_hash=hash_password(payload.password),
                email=payload.email,
                role=payload.role,
            )
        except sqlite3.IntegrityError as exc:
            message = str(exc).lower()
            if "users.email" in message or "email" in message:
                raise DuplicateUserEmail(payload.email) from exc
            if "users.username" in message or "username" in message:
                raise DuplicateUsername(payload.username) from exc
            raise InvalidUserReference("invalid user reference") from exc
        return UserResponse.model_validate(row)

    def get_user(self, user_id: str) -> UserResponse:
        user_id = user_id.strip()
        if not user_id:
            raise UserNotFound(user_id)
        row = get_user(user_id)
        if row is None:
            raise UserNotFound(user_id)
        return UserResponse.model_validate(row)

    def list_users(
        self,
        *,
        customer_id: str | None = None,
        limit: int = 100,
    ) -> UserListResponse:
        if customer_id is not None:
            customer_id = customer_id.strip()
            if not customer_id:
                raise InvalidUserReference("customer_id must not be empty")
            if get_customer(customer_id) is None:
                raise InvalidUserReference(f"customer not found: {customer_id}")

        total, rows = db_list_users(customer_id, limit)
        return UserListResponse(
            total=total,
            returned=len(rows),
            users=[UserResponse.model_validate(row) for row in rows],
        )
