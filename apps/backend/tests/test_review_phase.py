from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
import stripe
from fastapi import HTTPException
from httpx import AsyncClient

from app.auth import require_auth
from app.main import app
from app.middleware.auth import get_current_user, require_admin
from app.models import Order, Product, User


class _StripeSession:
    def __init__(self, session_id: str) -> None:
        self.id = session_id


def _mock_stripe(monkeypatch, session_id: str = "cs_test_123") -> None:
    monkeypatch.setattr(stripe.checkout.Session, "create", lambda **_: _StripeSession(session_id))


def _override(dep, fn):
    app.dependency_overrides[dep] = fn


def _clear_override(dep):
    app.dependency_overrides.pop(dep, None)


@pytest.mark.asyncio
async def test_protected_me_success(client: AsyncClient):
    _override(require_auth, lambda: {"sub": "user_123"})
    try:
        response = await client.get("/protected/me")
    finally:
        _clear_override(require_auth)

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "user_id": "user_123"}


@pytest.mark.asyncio
async def test_protected_me_unauthorized(client: AsyncClient):
    def _raise():
        raise HTTPException(status_code=401, detail="Missing bearer token")

    _override(require_auth, _raise)
    try:
        response = await client.get("/protected/me")
    finally:
        _clear_override(require_auth)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_users_me_unauthorized(client: AsyncClient):
    def _raise():
        raise HTTPException(status_code=401, detail="Invalid token")

    _override(get_current_user, _raise)
    try:
        response = await client.get("/users/me")
    finally:
        _clear_override(get_current_user)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_ping_redis_missing_env(client: AsyncClient, monkeypatch):
    monkeypatch.delenv("UPSTASH_REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)

    response = await client.get("/ping-redis")
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_orders_get_not_found(client: AsyncClient, db_session):
    user = User(
        clerk_id="clerk_user_1",
        email="user1@example.com",
        full_name="User One",
        role="user",
    )
    db_session.add(user)
    db_session.commit()

    _override(get_current_user, lambda: user)
    try:
        response = await client.get(f"/orders/{uuid4()}")
    finally:
        _clear_override(get_current_user)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_orders_get_forbidden(client: AsyncClient, db_session):
    owner = User(
        clerk_id="clerk_owner",
        email="owner@example.com",
        full_name="Owner",
        role="user",
    )
    other = User(
        clerk_id="clerk_other",
        email="other@example.com",
        full_name="Other",
        role="user",
    )
    db_session.add_all([owner, other])
    db_session.flush()

    order = Order(
        user_id=owner.id,
        status="pending",
        total_amount=Decimal("9.99"),
        promo_id=None,
        delivery_address={"street": "1 Main St"},
    )
    db_session.add(order)
    db_session.commit()

    _override(get_current_user, lambda: other)
    try:
        response = await client.get(f"/orders/{order.id}")
    finally:
        _clear_override(get_current_user)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_orders_create_missing_stripe(client: AsyncClient, db_session, monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)

    user = User(
        clerk_id="clerk_order_missing",
        email="missing@example.com",
        full_name="Missing Stripe",
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

    _override(get_current_user, lambda: user)
    try:
        response = await client.post(
            "/orders/",
            json={
                "items": [{"product_id": str(product.id), "quantity": 1}],
                "delivery_address": {"street": "1 Main St"},
            },
        )
    finally:
        _clear_override(get_current_user)

    assert response.status_code == 500


@pytest.mark.asyncio
async def test_orders_create_bad_payload(client: AsyncClient, db_session, monkeypatch):
    _mock_stripe(monkeypatch)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")

    user = User(
        clerk_id="clerk_bad_payload",
        email="bad@example.com",
        full_name="Bad Payload",
        role="user",
    )
    db_session.add(user)
    db_session.commit()

    _override(get_current_user, lambda: user)
    try:
        response = await client.post(
            "/orders/",
            json={"delivery_address": {"street": "1 Main St"}},
        )
    finally:
        _clear_override(get_current_user)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_orders_create_retry_not_idempotent(client: AsyncClient, db_session, monkeypatch):
    _mock_stripe(monkeypatch)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")

    user = User(
        clerk_id="clerk_retry",
        email="retry@example.com",
        full_name="Retry User",
        role="user",
    )
    product = Product(
        name="Pepperoni",
        description="Spicy",
        price=Decimal("14.00"),
        stock=10,
        is_available=True,
    )
    db_session.add_all([user, product])
    db_session.commit()

    payload = {
        "items": [{"product_id": str(product.id), "quantity": 1}],
        "delivery_address": {"street": "1 Main St"},
    }

    _override(get_current_user, lambda: user)
    try:
        response_a = await client.post("/orders/", json=payload)
        response_b = await client.post("/orders/", json=payload)
    finally:
        _clear_override(get_current_user)

    assert response_a.status_code == 200
    assert response_b.status_code == 200
    assert response_a.json()["id"] != response_b.json()["id"]


@pytest.mark.asyncio
async def test_orders_status_requires_admin(client: AsyncClient):
    def _raise():
        raise HTTPException(status_code=403, detail="Admin access required")

    _override(require_admin, _raise)
    try:
        response = await client.patch(f"/orders/{uuid4()}/status", json={"status": "delivered"})
    finally:
        _clear_override(require_admin)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_products_crud(client: AsyncClient):
    response = await client.post(
        "/products/",
        json={"name": "Truffle", "description": "Fancy", "price": "18.00", "stock": 5},
    )
    assert response.status_code == 201
    product = response.json()

    get_response = await client.get(f"/products/{product['id']}")
    assert get_response.status_code == 200

    update_response = await client.put(
        f"/products/{product['id']}",
        json={"price": "19.50", "stock": 3},
    )
    assert update_response.status_code == 200

    delete_response = await client.delete(f"/products/{product['id']}")
    assert delete_response.status_code == 204

    missing_response = await client.get(f"/products/{product['id']}")
    assert missing_response.status_code == 404


@pytest.mark.asyncio
async def test_products_not_found(client: AsyncClient):
    response = await client.get(f"/products/{uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_ml_churn_missing_model(client: AsyncClient):
    admin = User(
        clerk_id="clerk_admin",
        email="admin@example.com",
        full_name="Admin User",
        role="admin",
    )

    _override(require_admin, lambda: admin)
    try:
        response = await client.get(f"/ml/churn/{uuid4()}")
    finally:
        _clear_override(require_admin)

    assert response.status_code == 404
