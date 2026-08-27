"""Customer persistence models."""

import datetime
from pydantic import BaseModel



class Customer(BaseModel):
    id: str
    first_name: str
    last_name: str
    phone_number: str
    email: str
    status: str
    created_at: datetime
    updated_at: datetime
