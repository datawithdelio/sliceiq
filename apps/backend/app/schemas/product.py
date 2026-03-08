from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProductBase(BaseModel):
    name: str
    description: str | None = None
    price: Decimal
    stock: int


class ProductCreate(ProductBase):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Truffle Pizza",
                "description": "Mozzarella, mushrooms, truffle oil.",
                "price": "18.00",
                "stock": 12,
            }
        }
    )


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    price: Decimal | None = None
    stock: int | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "price": "19.50",
                "stock": 10,
            }
        }
    )


class ProductResponse(ProductBase):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "name": "Truffle Pizza",
                "description": "Mozzarella, mushrooms, truffle oil.",
                "price": "18.00",
                "stock": 12,
                "created_at": "2026-03-07T21:34:12.817256Z",
            }
        },
    )
