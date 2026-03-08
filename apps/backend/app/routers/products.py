from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"])


@router.get(
    "/",
    response_model=list[ProductResponse],
    summary="List products",
    description="Return products with pagination using `skip` and `limit`.",
)
def get_products(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[Product]:
    return db.query(Product).offset(skip).limit(limit).all()


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Get product by ID",
    responses={404: {"description": "Product not found"}},
)
def get_product(product_id: UUID, db: Session = Depends(get_db)) -> Product:
    product = db.query(Product).filter(Product.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post(
    "/",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create product",
    responses={201: {"description": "Product created"}},
)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)) -> Product:
    product = Product(
        name=payload.name,
        description=payload.description,
        price=payload.price,
        stock=payload.stock,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.put(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Update product",
    description="Update one or more product fields by product ID.",
    responses={404: {"description": "Product not found"}},
)
def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
) -> Product:
    product = db.query(Product).filter(Product.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(product, key, value)

    db.commit()
    db.refresh(product)
    return product


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete product",
    responses={404: {"description": "Product not found"}},
)
def delete_product(product_id: UUID, db: Session = Depends(get_db)) -> None:
    product = db.query(Product).filter(Product.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    db.delete(product)
    db.commit()
