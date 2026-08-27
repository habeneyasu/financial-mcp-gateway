"""Idempotency-key HTTP routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from financial_mcp_gateway.idempotency.schema import (
    IdempotencyKeyCreate,
    IdempotencyKeyListResponse,
    IdempotencyKeyResponse,
)
from financial_mcp_gateway.idempotency.service import (
    DuplicateIdempotencyKey,
    IdempotencyError,
    IdempotencyKeyNotFound,
    IdempotencyService,
    InvalidIdempotencyReference,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/idempotency-keys", tags=["idempotency"])


def get_idempotency_service() -> IdempotencyService:
    return IdempotencyService()


def _http_error(exc: IdempotencyError) -> HTTPException:
    if isinstance(exc, IdempotencyKeyNotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, DuplicateIdempotencyKey):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, InvalidIdempotencyReference):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "",
    response_model=IdempotencyKeyListResponse,
    summary="List idempotency keys",
)
def list_idempotency_keys(
    user_id: str | None = Query(default=None, description="Filter by user ID"),
    limit: int = Query(default=100, ge=1, le=100),
    service: IdempotencyService = Depends(get_idempotency_service),
) -> IdempotencyKeyListResponse:
    try:
        return service.list_keys(user_id=user_id, limit=limit)
    except IdempotencyError as exc:
        raise _http_error(exc) from exc
    except Exception:
        logger.exception("failed to list idempotency keys")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to list idempotency keys",
        ) from None


@router.post(
    "",
    response_model=IdempotencyKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create idempotency key",
)
def create_idempotency_key(
    payload: IdempotencyKeyCreate,
    service: IdempotencyService = Depends(get_idempotency_service),
) -> IdempotencyKeyResponse:
    try:
        return service.create_key(payload)
    except IdempotencyError as exc:
        raise _http_error(exc) from exc
    except Exception:
        logger.exception("failed to create idempotency key")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to create idempotency key",
        ) from None


@router.get(
    "/lookup",
    response_model=IdempotencyKeyResponse,
    summary="Get idempotency key",
)
def get_idempotency_key(
    user_id: str = Query(min_length=1),
    key: str = Query(min_length=1),
    service: IdempotencyService = Depends(get_idempotency_service),
) -> IdempotencyKeyResponse:
    try:
        return service.get_key(user_id, key)
    except IdempotencyError as exc:
        raise _http_error(exc) from exc
    except Exception:
        logger.exception("failed to get idempotency key %s/%s", user_id, key)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to get idempotency key",
        ) from None
