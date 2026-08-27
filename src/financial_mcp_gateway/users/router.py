"""User HTTP routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from financial_mcp_gateway.users.schema import UserCreate, UserListResponse, UserResponse
from financial_mcp_gateway.users.service import (
    DuplicateUserEmail,
    DuplicateUsername,
    InvalidUserReference,
    UserError,
    UserNotFound,
    UserService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


def get_user_service() -> UserService:
    return UserService()


def _http_error(exc: UserError) -> HTTPException:
    if isinstance(exc, UserNotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, (DuplicateUserEmail, DuplicateUsername)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, InvalidUserReference):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "",
    response_model=UserListResponse,
    summary="List users",
)
def list_users(
    customer_id: str | None = Query(default=None, description="Filter by customer ID"),
    limit: int = Query(default=100, ge=1, le=100),
    service: UserService = Depends(get_user_service),
) -> UserListResponse:
    try:
        return service.list_users(customer_id=customer_id, limit=limit)
    except UserError as exc:
        raise _http_error(exc) from exc
    except Exception:
        logger.exception("failed to list users")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to list users",
        ) from None


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create user",
)
def create_user(
    payload: UserCreate,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    try:
        return service.create_user(payload)
    except UserError as exc:
        raise _http_error(exc) from exc
    except Exception:
        logger.exception("failed to create user")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to create user",
        ) from None


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user",
)
def get_user(
    user_id: str,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    try:
        return service.get_user(user_id)
    except UserError as exc:
        raise _http_error(exc) from exc
    except Exception:
        logger.exception("failed to get user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to get user",
        ) from None
