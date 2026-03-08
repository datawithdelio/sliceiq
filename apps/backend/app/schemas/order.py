from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OrderItemBase(BaseModel):
    product_id: UUID
    quantity: int
    customizations: Optional[dict] = None


class OrderCreate(BaseModel):
    items: list[OrderItemBase]
    promo_code: Optional[str] = None
    delivery_address: dict


class OrderStatusUpdate(BaseModel):
    status: str


class OrderResponse(BaseModel):
    id: UUID
    user_id: UUID
    status: str
    total_amount: float
    promo_id: Optional[UUID]
    delivery_address: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
