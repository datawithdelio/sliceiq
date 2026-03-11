from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user as get_current_user_id
from app.database import get_db
from app.middleware.auth import get_current_user, require_admin
from app.models import Order, OrderItem, Product, User
from app.schemas.order import (
    OrderCreate,
    OrderCreateResponse,
    OrderResponse,
    OrderStatusUpdate,
    OrderWithItemsResponse,
    ReorderResponse,
)
from app.services.order_saga import OrderSaga

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/", response_model=OrderCreateResponse)
async def create_order(
    order_data: OrderCreate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> Order:
    current_user = db.query(User).filter(User.clerk_id == user_id).first()
    if not current_user:
        raise HTTPException(status_code=401, detail="User not found")

    saga = OrderSaga(db)
    order, checkout_url = await saga.create_order_transaction(
        order_data=order_data,
        current_user=current_user,
    )

    db.refresh(order)
    return {"order": order, "checkout_url": checkout_url}


def _get_user_by_clerk_id(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.clerk_id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@router.get("/", response_model=list[OrderResponse])
def get_user_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Order]:
    result = db.execute(
        select(Order).where(Order.user_id == current_user.id).order_by(Order.created_at.desc())
    )
    return result.scalars().all()


@router.get("/history", response_model=list[OrderWithItemsResponse])
def get_order_history(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> list[Order]:
    user = _get_user_by_clerk_id(db, user_id)
    result = db.execute(
        select(Order)
        .options(selectinload(Order.order_items))
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
    )
    orders = result.scalars().all()
    return orders


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


@router.post("/{order_id}/reorder", response_model=ReorderResponse)
def reorder_from_history(
    order_id: UUID,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict[str, object]:
    user = _get_user_by_clerk_id(db, user_id)
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    cart_items = []
    unavailable = []

    for item in items:
        product = db.get(Product, item.product_id)
        if not product or not product.is_available:
            unavailable.append(item.product_id)
            continue
        cart_items.append(
            {
                "product_id": item.product_id,
                "quantity": item.quantity,
                "customizations": item.customizations,
            }
        )

    return {
        "order_id": order.id,
        "items": cart_items,
        "unavailable_items": unavailable,
    }
