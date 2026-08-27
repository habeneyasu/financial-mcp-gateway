"""Customer business logic."""

from __future__ import annotations

import sqlite3
import uuid

from db import get_customer, insert_customer
from financial_mcp_gateway.customers.schema import CustomerCreate, CustomerResponse


class CustomerError(Exception):
    """Base error for customer operations."""


class CustomerNotFound(CustomerError):
    def __init__(self, customer_id: str) -> None:
        self.customer_id = customer_id
        super().__init__(f"customer not found: {customer_id}")


class DuplicateCustomerEmail(CustomerError):
    def __init__(self, email: str) -> None:
        self.email = email
        super().__init__(f"customer email already exists: {email}")


class CustomerService:
    def create_customer(self, payload: CustomerCreate) -> CustomerResponse:
        customer_id = f"cust-{uuid.uuid4().hex[:12]}"
        try:
            row = insert_customer(
                customer_id=customer_id,
                first_name=payload.first_name,
                last_name=payload.last_name,
                phone_number=payload.phone_number,
                email=payload.email,
                status=payload.status,
                created_by=payload.created_by,
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateCustomerEmail(payload.email) from exc
        return CustomerResponse.model_validate(row)

    def get_customer(self, customer_id: str) -> CustomerResponse:
        customer_id = customer_id.strip()
        if not customer_id:
            raise CustomerNotFound(customer_id)
        row = get_customer(customer_id)
        if row is None:
            raise CustomerNotFound(customer_id)
        return CustomerResponse.model_validate(row)
