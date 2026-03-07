from __future__ import annotations

import os
import random
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from dotenv import load_dotenv
from faker import Faker
from sqlalchemy import delete, insert, select, text

# Allow direct execution: `python scripts/seed_data.py`
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.user import User


TARGET_USERS = 200
POWER_USER_RATIO = 0.30
SYNTHETIC_DOMAIN = "synthetic.sliceiq.local"


@dataclass
class ProductSnapshot:
    id: int
    price: Decimal


def _weighted_order_timestamp(start_at: datetime, end_at: datetime) -> datetime:
    # Day weights: busier weekdays, slower weekends.
    day_weights = {
        0: 1.20,  # Mon
        1: 1.20,  # Tue
        2: 1.10,  # Wed
        3: 1.10,  # Thu
        4: 1.15,  # Fri
        5: 0.75,  # Sat
        6: 0.70,  # Sun
    }

    # Hour weights: lunch (12-14) and dinner (18-21) peaks.
    hour_weights = {
        0: 0.15,
        1: 0.10,
        2: 0.10,
        3: 0.10,
        4: 0.10,
        5: 0.15,
        6: 0.25,
        7: 0.40,
        8: 0.55,
        9: 0.65,
        10: 0.85,
        11: 1.20,
        12: 1.70,
        13: 1.80,
        14: 1.45,
        15: 0.90,
        16: 0.95,
        17: 1.25,
        18: 1.90,
        19: 2.00,
        20: 1.85,
        21: 1.35,
        22: 0.75,
        23: 0.35,
    }

    while True:
        total_seconds = int((end_at - start_at).total_seconds())
        candidate = start_at + timedelta(seconds=random.randint(0, total_seconds))
        if random.random() <= day_weights[candidate.weekday()] / 1.20:
            break

    hours = list(range(24))
    weights = [hour_weights[h] for h in hours]
    hour = random.choices(hours, weights=weights, k=1)[0]
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return candidate.replace(hour=hour, minute=minute, second=second, microsecond=0)


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def main() -> None:
    load_dotenv()
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required in environment/.env")

    faker = Faker()
    random.seed(42)
    Faker.seed(42)

    now = datetime.now(UTC)
    six_months_ago = now - timedelta(days=180)

    with SessionLocal() as db:
        # Ensure products exist first (required for order_items).
        products_raw = db.execute(select(Product.id, Product.price)).all()
        if not products_raw:
            raise RuntimeError("No products found. Seed products first.")
        products = [ProductSnapshot(id=row[0], price=Decimal(row[1])) for row in products_raw]

        # 1) Users: idempotent insert up to TARGET_USERS using a synthetic email domain.
        existing_synth_users = db.execute(
            select(User.id, User.email).where(User.email.like(f"%@{SYNTHETIC_DOMAIN}"))
        ).all()
        existing_count = len(existing_synth_users)
        users_to_create = max(0, TARGET_USERS - existing_count)

        new_user_payloads: list[dict[str, object]] = []
        if users_to_create:
            taken_emails = {row[1] for row in existing_synth_users}
            next_idx = 1
            while len(new_user_payloads) < users_to_create:
                candidate_email = f"user{next_idx:04d}@{SYNTHETIC_DOMAIN}"
                next_idx += 1
                if candidate_email in taken_emails:
                    continue
                created_at = six_months_ago + timedelta(
                    seconds=random.randint(0, int((now - six_months_ago).total_seconds()))
                )
                new_user_payloads.append(
                    {
                        "name": faker.name(),
                        "email": candidate_email,
                        "created_at": created_at,
                    }
                )
                taken_emails.add(candidate_email)

            db.execute(insert(User), new_user_payloads)
            db.commit()

        users = db.execute(
            select(User.id, User.created_at).where(User.email.like(f"%@{SYNTHETIC_DOMAIN}"))
        ).all()
        user_ids = [row[0] for row in users]
        user_created_at_map = {row[0]: row[1] for row in users}

        # 2) Orders/Order Items: idempotent re-run by removing prior synthetic-user orders.
        synthetic_order_ids = db.execute(
            select(Order.id).where(Order.user_id.in_(user_ids))
        ).scalars().all()
        if synthetic_order_ids:
            db.execute(delete(OrderItem).where(OrderItem.order_id.in_(synthetic_order_ids)))
            db.execute(delete(Order).where(Order.id.in_(synthetic_order_ids)))
            db.commit()

        # Behavioral split: ~30% power users, rest occasional.
        power_count = max(1, int(len(user_ids) * POWER_USER_RATIO))
        power_user_ids = set(random.sample(user_ids, k=power_count))

        order_rows: list[dict[str, object]] = []
        for uid in user_ids:
            if uid in power_user_ids:
                order_target = random.randint(8, 24)
            else:
                # Occasional users place a single order in this simulation.
                order_target = 1

            user_start = max(six_months_ago, user_created_at_map[uid])
            for _ in range(order_target):
                created_at = _weighted_order_timestamp(user_start, now)
                order_rows.append(
                    {
                        "user_id": uid,
                        "total_price": Decimal("0.00"),
                        "status": random.choices(
                            ["pending", "completed", "cancelled"],
                            weights=[0.10, 0.85, 0.05],
                            k=1,
                        )[0],
                        "created_at": created_at,
                    }
                )

        inserted_orders = db.execute(
            insert(Order).returning(Order.id, Order.user_id, Order.created_at),
            order_rows,
        ).all()

        # Create order_items (1-5 items/order) and compute order totals.
        order_item_rows: list[dict[str, object]] = []
        order_totals: dict[int, Decimal] = {}
        for order_id, _uid, _created_at in inserted_orders:
            item_count = random.randint(1, 5)
            selected_products = random.choices(products, k=item_count)
            total = Decimal("0.00")
            for product in selected_products:
                quantity = random.randint(1, 3)
                # Mild price drift to simulate promos/price changes.
                drift = Decimal(str(random.uniform(-0.08, 0.12)))
                unit_price = _money(product.price * (Decimal("1.00") + drift))
                if unit_price <= 0:
                    unit_price = Decimal("1.00")
                total += unit_price * quantity
                order_item_rows.append(
                    {
                        "order_id": order_id,
                        "product_id": product.id,
                        "quantity": quantity,
                        "unit_price": unit_price,
                    }
                )
            order_totals[order_id] = _money(total)

        if order_item_rows:
            db.execute(insert(OrderItem), order_item_rows)

        # Update totals in one batch-ish pass.
        for oid, total in order_totals.items():
            db.execute(
                Order.__table__.update().where(Order.id == oid).values(total_price=total)
            )

        db.commit()

        metrics = db.execute(
            text(
                """
                WITH s_orders AS (
                    SELECT o.*
                    FROM orders o
                    JOIN users u ON u.id = o.user_id
                    WHERE u.email LIKE :pattern
                )
                SELECT
                    COUNT(*) AS total_orders,
                    ROUND(
                        100.0 * SUM(
                            CASE
                                WHEN EXTRACT(HOUR FROM created_at) BETWEEN 12 AND 13
                                  OR EXTRACT(HOUR FROM created_at) BETWEEN 18 AND 20
                                THEN 1 ELSE 0
                            END
                        ) / COUNT(*),
                        2
                    ) AS rush_hour_pct,
                    ROUND(
                        100.0 * SUM(
                            CASE WHEN EXTRACT(ISODOW FROM created_at) BETWEEN 1 AND 5 THEN 1 ELSE 0 END
                        ) / COUNT(*),
                        2
                    ) AS weekday_pct,
                    ROUND(
                        100.0 * SUM(
                            CASE WHEN EXTRACT(ISODOW FROM created_at) IN (6, 7) THEN 1 ELSE 0 END
                        ) / COUNT(*),
                        2
                    ) AS weekend_pct
                FROM s_orders;
                """
            ),
            {"pattern": f"%@{SYNTHETIC_DOMAIN}"},
        ).mappings().one()

        repeat_metrics = db.execute(
            text(
                """
                WITH user_order_counts AS (
                    SELECT u.id, COUNT(o.id) AS c
                    FROM users u
                    LEFT JOIN orders o ON o.user_id = u.id
                    WHERE u.email LIKE :pattern
                    GROUP BY u.id
                )
                SELECT
                    COUNT(*) AS total_users,
                    SUM(CASE WHEN c > 1 THEN 1 ELSE 0 END) AS repeat_users,
                    ROUND(100.0 * SUM(CASE WHEN c > 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS repeat_user_pct,
                    SUM(CASE WHEN c >= 8 THEN 1 ELSE 0 END) AS power_users,
                    ROUND(100.0 * SUM(CASE WHEN c >= 8 THEN 1 ELSE 0 END) / COUNT(*), 2) AS power_user_pct
                FROM user_order_counts;
                """
            ),
            {"pattern": f"%@{SYNTHETIC_DOMAIN}"},
        ).mappings().one()

        print(f"Seeded {len(user_ids)} users, {len(inserted_orders)} orders, {len(order_item_rows)} order_items")
        print(
            "Behavior Report: "
            f"rush_hour_pct={metrics['rush_hour_pct']}%, "
            f"weekday_pct={metrics['weekday_pct']}%, "
            f"weekend_pct={metrics['weekend_pct']}%, "
            f"repeat_user_pct={repeat_metrics['repeat_user_pct']}%, "
            f"power_user_pct={repeat_metrics['power_user_pct']}%"
        )


if __name__ == "__main__":
    main()
