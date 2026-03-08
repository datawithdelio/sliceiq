import pytest
from httpx import AsyncClient

from app.main import app
from app.middleware.auth import get_current_user
from app.models import User


@pytest.mark.asyncio
async def test_get_current_user_profile(client: AsyncClient, db_session):
    user = User(
        clerk_id="clerk_test",
        email="user@example.com",
        full_name="Test User",
        role="user",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    app.dependency_overrides[get_current_user] = lambda: user
    try:
        response = await client.get("/users/me")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "user@example.com"
    assert data["full_name"] == "Test User"


@pytest.mark.asyncio
async def test_update_profile(client: AsyncClient, db_session):
    user = User(
        clerk_id="clerk_update",
        email="update@example.com",
        full_name="Before",
        role="user",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    app.dependency_overrides[get_current_user] = lambda: user
    try:
        response = await client.put(
            "/users/me",
            json={"full_name": "After", "avatar_url": "https://example.com/a.png"},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "After"
    assert data["avatar_url"] == "https://example.com/a.png"
