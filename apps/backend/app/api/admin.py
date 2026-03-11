from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.socket_manager import socket_manager
from app.database import get_db
from app.models import Order, User
from app.schemas.order import AdminOrderResponse, AdminOrderStatusUpdate

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)


def _require_admin(db: Session, clerk_id: str) -> User:
    user = db.query(User).filter(User.clerk_id == clerk_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/orders", response_model=list[AdminOrderResponse])
def list_all_orders(
    db: Session = Depends(get_db),
    clerk_id: str = Depends(get_current_user),
) -> list[Order]:
    _require_admin(db, clerk_id)
    result = db.execute(
        select(Order)
        .options(selectinload(Order.user))
        .order_by(Order.created_at.desc())
    )
    return result.scalars().all()


@router.patch("/orders/{order_id}/status", response_model=AdminOrderResponse)
async def update_order_status_admin(
    order_id: UUID,
    payload: AdminOrderStatusUpdate,
    db: Session = Depends(get_db),
    clerk_id: str = Depends(get_current_user),
) -> Order:
    _require_admin(db, clerk_id)
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.status = payload.new_status
    db.commit()
    db.refresh(order)

    user_room = None
    if order.user and order.user.clerk_id:
        user_room = order.user.clerk_id

    if user_room:
        try:
            await socket_manager.emit_order_update(
                user_id=user_room,
                data={
                    "order_id": str(order.id),
                    "status": order.status,
                    "message": f"Order status updated to {order.status}.",
                },
            )
        except Exception as exc:
            logger.exception("Failed to emit order update: %s", exc)

    return order
