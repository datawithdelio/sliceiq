from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import os
from uuid import UUID

import stripe
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user, require_admin
from app.models import Order, OrderItem, Product, Promo, User
from app.schemas.order import OrderCreate, OrderResponse, OrderStatusUpdate

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/", response_model=OrderResponse)
def create_order(
    order_data: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Order:
    total = Decimal("0")
    items: list[dict] = []

    for item in order_data.items:
        product = db.get(Product, item.product_id)
        if not product or not product.is_available:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not available")
        total += product.price * item.quantity
        items.append(
            {
                "product_id": item.product_id,
                "quantity": item.quantity,
                "unit_price": product.price,
                "customizations": item.customizations,
            }
        )

    promo_id = None
    if order_data.promo_code:
        result = db.execute(
            select(Promo).where(Promo.code == order_data.promo_code, Promo.is_active.is_(True))
        )
        promo = result.scalar_one_or_none()
        if promo and (not promo.expires_at or promo.expires_at > datetime.utcnow()):
            if not promo.max_uses or promo.used_count < promo.max_uses:
                discount = promo.discount_pct / Decimal("100")
                total = total * (Decimal("1") - discount)
                promo_id = promo.id
                promo.used_count += 1

    order = Order(
        user_id=current_user.id,
        status="pending",
        total_amount=total,
        promo_id=promo_id,
        delivery_address=order_data.delivery_address,
    )
    db.add(order)
    db.flush()

    for item in items:
        db.add(OrderItem(order_id=order.id, **item))

    stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe is not configured")

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": "Order from SliceIQ"},
                    "unit_amount": int(total * 100),
                },
                "quantity": 1,
            }
        ],
        mode="payment",
        success_url=f"{frontend_url}/orders/success",
        cancel_url=f"{frontend_url}/cart",
        metadata={"order_id": str(order.id)},
    )

    order.stripe_session_id = session.id
    db.commit()
    db.refresh(order)

    return order


@router.get("/", response_model=list[OrderResponse])
def get_user_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Order]:
    result = db.execute(
        select(Order).where(Order.user_id == current_user.id).order_by(Order.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Order:
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    return order


@router.patch("/{order_id}/status")
def update_order_status(
    order_id: UUID,
    status_update: OrderStatusUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict[str, str]:
    _ = admin
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.status = status_update.status
    db.commit()

    return {"message": f"Order status updated to {status_update.status}"}
