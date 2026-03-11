from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import logging
from typing import Tuple
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.socket_manager import socket_manager
from app.models import Order, OrderItem, Product, Promo, User
from app.schemas.order import OrderCreate
from app.services.stripe_service import create_checkout_session

logger = logging.getLogger(__name__)


class OrderSaga:
    def __init__(self, db: Session) -> None:
        self.db = db

    async def create_order_transaction(self, *, order_data: OrderCreate, current_user: User) -> Tuple[Order, str]:
        with self.db.begin():
            total = Decimal("0")
            items: list[dict] = []

            for item in order_data.items:
                product = self.db.get(Product, item.product_id)
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
                result = self.db.execute(
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
            self.db.add(order)
            self.db.flush()

            for item in items:
                self.db.add(OrderItem(order_id=order.id, **item))

            session = create_checkout_session(order_id=str(order.id), total=total)

            order.stripe_session_id = session.id

            checkout_url = getattr(session, "url", None)
            if not checkout_url:
                checkout_url = f"https://checkout.stripe.test/session/{session.id}"

            order_payload = {
                "order_id": str(order.id),
                "status": order.status,
                "message": "Your order has been placed successfully!",
            }
            user_room = current_user.clerk_id or str(order.user_id)
            try:
                await socket_manager.emit_order_update(user_id=str(user_room), data=order_payload)
            except Exception as exc:
                logger.exception("Failed to emit order update: %s", exc)

            return order, checkout_url
