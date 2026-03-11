from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Literal


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


class OrderItemResponse(BaseModel):
    product_id: UUID
    quantity: int
    unit_price: float
    customizations: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)


class OrderWithItemsResponse(OrderResponse):
    items: list[OrderItemResponse]


class ReorderCartItem(BaseModel):
    product_id: UUID
    quantity: int
    customizations: Optional[dict] = None


class ReorderResponse(BaseModel):
    order_id: UUID
    items: list[ReorderCartItem]
    unavailable_items: list[UUID]


class AdminOrderUser(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class AdminOrderResponse(BaseModel):
    id: UUID
    user: AdminOrderUser
    status: str
    total_amount: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminOrderStatusUpdate(BaseModel):
    new_status: Literal["processing", "out_for_delivery", "delivered", "cancelled"]


class OrderCreateResponse(BaseModel):
    order: OrderResponse
    checkout_url: str
