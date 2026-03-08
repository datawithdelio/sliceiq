from decimal import Decimal

import pytest
import stripe
from httpx import AsyncClient

from app.main import app
from app.middleware.auth import get_current_user
from app.models import Order, Product, User


class _StripeSession:
    id = "cs_test_123"


def _mock_stripe(monkeypatch):
    monkeypatch.setattr(stripe.checkout.Session, "create", lambda **_: _StripeSession())


@pytest.mark.asyncio
async def test_create_order(client: AsyncClient, db_session, monkeypatch):
    _mock_stripe(monkeypatch)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")

    user = User(
        clerk_id="clerk_order",
        email="order@example.com",
        full_name="Order User",
        role="user",
    )
    product = Product(
        name="Margherita",
        description="Classic",
        price=Decimal("12.50"),
        stock=10,
        is_available=True,
    )
    db_session.add_all([user, product])
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(product)

    app.dependency_overrides[get_current_user] = lambda: user
    try:
        response = await client.post(
            "/orders/",
            json={
                "items": [{"product_id": str(product.id), "quantity": 2}],
                "delivery_address": {"street": "1 Main St"},
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(user.id)
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_update_order_status_admin(client: AsyncClient, db_session):
    admin = User(
        clerk_id="clerk_admin",
        email="admin@example.com",
        full_name="Admin User",
        role="admin",
    )
    db_session.add(admin)
    db_session.flush()

    order = Order(
        user_id=admin.id,
        status="pending",
        total_amount=Decimal("10.00"),
        promo_id=None,
        delivery_address={"street": "1 Main St"},
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        response = await client.patch(
            f"/orders/{order.id}/status",
            json={"status": "delivered"},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Order status updated to delivered"
