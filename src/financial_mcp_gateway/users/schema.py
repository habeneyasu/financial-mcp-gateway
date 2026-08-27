"""User request and response schemas."""

from pydantic import BaseModel, Field, field_validator

_ALLOWED_ROLES = {"admin", "member"}


class UserCreate(BaseModel):
    customer_id: str = Field(min_length=1, max_length=64)
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    email: str = Field(min_length=3, max_length=255)
    role: str = "member"

    @field_validator("customer_id", "username", "email", "role", mode="before")
    @classmethod
    def strip_required(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("email")
    @classmethod
    def email_has_at(cls, value: str) -> str:
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("email must be a valid address")
        return value.lower()

    @field_validator("role")
    @classmethod
    def role_allowed(cls, value: str) -> str:
        if value not in _ALLOWED_ROLES:
            raise ValueError("role must be admin or member")
        return value


class UserResponse(BaseModel):
    id: str
    customer_id: str
    username: str
    email: str
    role: str
    created_at: str


class UserListResponse(BaseModel):
    total: int
    returned: int
    users: list[UserResponse]
