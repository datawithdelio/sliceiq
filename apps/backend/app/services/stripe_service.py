from __future__ import annotations

import os
from decimal import Decimal
from typing import Optional

import stripe
from fastapi import HTTPException


def _stripe_api_key() -> str:
    api_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=500, detail="Stripe is not configured")
    return api_key


def create_checkout_session(*, order_id: str, total: Decimal) -> stripe.checkout.Session:
    stripe.api_key = _stripe_api_key()

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    success_url = (
        f"{frontend_url}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}&order_id={order_id}"
    )
    cancel_url = f"{frontend_url}/cart"

    return stripe.checkout.Session.create(
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
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"order_id": order_id},
    )


def retrieve_checkout_session(session_id: str) -> stripe.checkout.Session:
    stripe.api_key = _stripe_api_key()
    return stripe.checkout.Session.retrieve(session_id)
