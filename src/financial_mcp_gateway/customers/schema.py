"""Customer request and response schemas."""

from pydantic import BaseModel, Field, field_validator

_ALLOWED_STATUSES = {"active", "inactive"}


class CustomerCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone_number: str = Field(min_length=1, max_length=32)
    email: str = Field(min_length=3, max_length=255)
    status: str = "active"
    created_by: str | None = None

    @field_validator("first_name", "last_name", "phone_number", "email", "status", mode="before")
    @classmethod
    def strip_required(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("created_by", mode="before")
    @classmethod
    def strip_optional(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("email")
    @classmethod
    def email_has_at(cls, value: str) -> str:
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("email must be a valid address")
        return value.lower()

    @field_validator("status")
    @classmethod
    def status_allowed(cls, value: str) -> str:
        if value not in _ALLOWED_STATUSES:
            raise ValueError("status must be active or inactive")
        return value


class CustomerResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    phone_number: str
    email: str
    status: str
    created_by: str | None = None
    created_at: str
