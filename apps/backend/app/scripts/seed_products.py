from __future__ import annotations

from decimal import Decimal

from app.database import SessionLocal
from app.models import Product


def seed_products() -> None:
    db = SessionLocal()
    try:
        existing = db.query(Product).count()
        if existing > 0:
            print(f"Skipping seed: {existing} products already exist.")
            return

        products = [
            Product(
                name="Margherita Pizza",
                description="Classic tomato sauce, mozzarella, and basil.",
                price=Decimal("12.99"),
                stock=50,
            ),
            Product(
                name="Pepperoni Pizza",
                description="Mozzarella, tomato sauce, and pepperoni slices.",
                price=Decimal("14.99"),
                stock=40,
            ),
            Product(
                name="Veggie Supreme",
                description="Bell peppers, onions, olives, mushrooms, and cheese.",
                price=Decimal("13.49"),
                stock=35,
            ),
            Product(
                name="BBQ Chicken Pizza",
                description="BBQ sauce, grilled chicken, red onions, and cilantro.",
                price=Decimal("15.49"),
                stock=25,
            ),
            Product(
                name="Garlic Knots",
                description="Fresh baked knots tossed in garlic butter and herbs.",
                price=Decimal("6.99"),
                stock=100,
            ),
        ]

        db.add_all(products)
        db.commit()
        print("Seeded 5 products.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_products()

