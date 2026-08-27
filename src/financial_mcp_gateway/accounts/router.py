"""Account HTTP routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from financial_mcp_gateway.accounts.schema import AccountCreate, AccountResponse
from financial_mcp_gateway.accounts.service import (
    AccountError,
    AccountNotFound,
    AccountService,
    DuplicateAccountNumber,
    InvalidAccountReference,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/accounts", tags=["accounts"])


def get_account_service() -> AccountService:
    return AccountService()


def _http_error(exc: AccountError) -> HTTPException:
    if isinstance(exc, AccountNotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, DuplicateAccountNumber):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, InvalidAccountReference):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create account",
)
def create_account(
    payload: AccountCreate,
    service: AccountService = Depends(get_account_service),
) -> AccountResponse:
    try:
        return service.create_account(payload)
    except AccountError as exc:
        raise _http_error(exc) from exc
    except Exception:
        logger.exception("failed to create account")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to create account",
        ) from None


@router.get(
    "/{account_id}",
    response_model=AccountResponse,
    summary="Get account",
)
def get_account(
    account_id: str,
    service: AccountService = Depends(get_account_service),
) -> AccountResponse:
    try:
        return service.get_account(account_id)
    except AccountError as exc:
        raise _http_error(exc) from exc
    except Exception:
        logger.exception("failed to get account %s", account_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to get account",
        ) from None
