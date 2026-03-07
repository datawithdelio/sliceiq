from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class OrderBase(BaseModel):
    user_id: int
    total_price: Decimal
    status: str


class OrderCreate(OrderBase):
    pass


class OrderResponse(OrderBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

