"""Customer HTTP routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from financial_mcp_gateway.customers.schema import CustomerCreate, CustomerResponse
from financial_mcp_gateway.customers.service import (
    CustomerError,
    CustomerNotFound,
    CustomerService,
    DuplicateCustomerEmail,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/customers", tags=["customers"])


def get_customer_service() -> CustomerService:
    return CustomerService()


def _http_error(exc: CustomerError) -> HTTPException:
    if isinstance(exc, CustomerNotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, DuplicateCustomerEmail):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create customer",
)
def create_customer(
    payload: CustomerCreate,
    service: CustomerService = Depends(get_customer_service),
) -> CustomerResponse:
    try:
        return service.create_customer(payload)
    except CustomerError as exc:
        raise _http_error(exc) from exc
    except Exception:
        logger.exception("failed to create customer")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to create customer",
        ) from None


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Get customer",
)
def get_customer(
    customer_id: str,
    service: CustomerService = Depends(get_customer_service),
) -> CustomerResponse:
    try:
        return service.get_customer(customer_id)
    except CustomerError as exc:
        raise _http_error(exc) from exc
    except Exception:
        logger.exception("failed to get customer %s", customer_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to get customer",
        ) from None
