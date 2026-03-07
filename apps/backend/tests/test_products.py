from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.product import Product


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def _reset_products() -> None:
    db: Session = TestingSessionLocal()
    try:
        db.query(Product).delete()
        db.commit()
    finally:
        db.close()


def _seed_products(count: int) -> None:
    db: Session = TestingSessionLocal()
    try:
        for i in range(count):
            db.add(
                Product(
                    name=f"Product {i + 1}",
                    description=f"Desc {i + 1}",
                    price=Decimal("9.99"),
                    stock=10 + i,
                )
            )
        db.commit()
    finally:
        db.close()


def test_get_products_pagination() -> None:
    _reset_products()
    _seed_products(5)

    response = client.get("/products/?skip=1&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "Product 2"
    assert data[1]["name"] == "Product 3"


def test_get_product_by_id() -> None:
    _reset_products()
    _seed_products(1)

    response = client.get("/products/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Product 1"


def test_create_product() -> None:
    _reset_products()

    payload = {
        "name": "Hawaiian Pizza",
        "description": "Pineapple and ham.",
        "price": "16.50",
        "stock": 8,
    }
    response = client.post("/products/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["price"] == payload["price"]
    assert data["stock"] == payload["stock"]


def test_update_product() -> None:
    _reset_products()
    _seed_products(1)

    payload = {
        "name": "Updated Product 1",
        "price": "11.49",
        "stock": 99,
    }
    response = client.put("/products/1", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == payload["name"]
    assert data["price"] == payload["price"]
    assert data["stock"] == payload["stock"]


def test_delete_product() -> None:
    _reset_products()
    _seed_products(1)

    response = client.delete("/products/1")
    assert response.status_code == 204

    fetch = client.get("/products/1")
    assert fetch.status_code == 404
