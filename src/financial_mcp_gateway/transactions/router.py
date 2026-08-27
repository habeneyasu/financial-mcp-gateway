"""Transaction HTTP routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from financial_mcp_gateway.transactions.schema import (
    TransactionCreate,
    TransactionListResponse,
    TransactionResponse,
)
from financial_mcp_gateway.transactions.service import (
    DuplicateTransactionReference,
    InvalidTransactionReference,
    TransactionAccountNotFound,
    TransactionError,
    TransactionNotFound,
    TransactionService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transactions", tags=["transactions"])


def get_transaction_service() -> TransactionService:
    return TransactionService()


def _http_error(exc: TransactionError) -> HTTPException:
    if isinstance(exc, TransactionNotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, DuplicateTransactionReference):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, (TransactionAccountNotFound, InvalidTransactionReference)):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "",
    response_model=TransactionListResponse,
    summary="List transactions",
)
def list_transactions(
    account_id: str | None = Query(default=None, description="Filter by account ID"),
    limit: int = Query(default=10, ge=1, le=100),
    service: TransactionService = Depends(get_transaction_service),
) -> TransactionListResponse:
    try:
        return service.list_transactions(account_id=account_id, limit=limit)
    except TransactionError as exc:
        raise _http_error(exc) from exc
    except Exception:
        logger.exception("failed to list transactions")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to list transactions",
        ) from None


@router.post(
    "",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create transaction",
)
def create_transaction(
    payload: TransactionCreate,
    service: TransactionService = Depends(get_transaction_service),
) -> TransactionResponse:
    try:
        return service.create_transaction(payload)
    except TransactionError as exc:
        raise _http_error(exc) from exc
    except Exception:
        logger.exception("failed to create transaction")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to create transaction",
        ) from None


@router.get(
    "/{reference}",
    response_model=TransactionResponse,
    summary="Get transaction by reference",
)
def get_transaction(
    reference: str,
    service: TransactionService = Depends(get_transaction_service),
) -> TransactionResponse:
    try:
        return service.get_transaction(reference)
    except TransactionError as exc:
        raise _http_error(exc) from exc
    except Exception:
        logger.exception("failed to get transaction %s", reference)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to get transaction",
        ) from None
