from __future__ import annotations

import logging
import os

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import JWTBearer
from app.database import get_db
from app.models import Order, User
from app.core.socket_manager import socket_manager
from app.services.stripe_service import retrieve_checkout_session

router = APIRouter(prefix="/payments", tags=["payments"])
logger = logging.getLogger(__name__)


@router.get("/verify/{session_id}")
def verify_payment(
    session_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(JWTBearer()),
) -> dict[str, str]:
    session = retrieve_checkout_session(session_id)

    payment_status = getattr(session, "payment_status", None)
    if payment_status not in {"paid", "no_payment_required"}:
        raise HTTPException(status_code=402, detail="Payment not completed")

    metadata = getattr(session, "metadata", {}) or {}
    order_id = metadata.get("order_id")
    if not order_id:
        raise HTTPException(status_code=400, detail="Order metadata missing")

    user = db.query(User).filter(User.clerk_id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    order.status = "processing"
    db.commit()

    return {"status": "verified", "order_id": str(order.id)}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> dict[str, str]:
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    if not webhook_secret:
        raise HTTPException(status_code=500, detail="STRIPE_WEBHOOK_SECRET is not configured")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")

    try:
        event = stripe.Webhook.construct_event(payload=payload, sig_header=signature, secret=webhook_secret)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Webhook signature verification failed: {exc}") from exc

    event_type = event.get("type", "unknown")
    logger.info("Stripe webhook received: %s", event_type)

    if event_type == "checkout.session.completed":
        session = event.get("data", {}).get("object", {}) or {}
        metadata = session.get("metadata", {}) or {}
        order_id = metadata.get("order_id") or session.get("client_reference_id")
        if not order_id:
            raise HTTPException(status_code=400, detail="Order metadata missing")

        order = db.get(Order, order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        order.status = "processing"
        db.commit()

        user_room = None
        if order.user and order.user.clerk_id:
            user_room = order.user.clerk_id
        else:
            user_room = str(order.user_id)

        try:
            await socket_manager.emit_order_update(
                user_id=user_room,
                data={
                    "order_id": str(order.id),
                    "status": "processing",
                    "message": "Payment confirmed! We are preparing your order.",
                },
            )
        except Exception as exc:
            logger.exception("Failed to emit order update: %s", exc)

        customer_name = None
        if order.user and order.user.full_name:
            customer_name = order.user.full_name
        else:
            user = db.query(User).filter(User.id == order.user_id).first()
            customer_name = user.full_name if user else "Customer"

        try:
            await socket_manager.sio.emit(
                "new_order_admin",
                {
                    "order_id": str(order.id),
                    "customer_name": customer_name,
                    "total": float(order.total_amount),
                },
                room="admin_room",
            )
        except Exception as exc:
            logger.exception("Failed to emit admin order update: %s", exc)

    return {"status": "ok"}
