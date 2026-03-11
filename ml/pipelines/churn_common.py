from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import os
from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine


DEFAULT_HISTORY_DAYS = 180
DEFAULT_LABEL_DAYS = 30


@dataclass(frozen=True)
class SchemaProfile:
    order_amount_column: str
    has_order_items: bool
    has_reviews: bool
    has_order_status: bool
    has_promo_id: bool


def get_database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5433/sliceiq",
    )


def create_db_engine(database_url: str | None = None) -> Engine:
    return create_engine(database_url or get_database_url(), pool_pre_ping=True)


def _as_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC)


def _profile_schema(engine: Engine) -> SchemaProfile:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    required_tables = {"users", "orders"}
    missing_tables = sorted(required_tables - table_names)
    if missing_tables:
        raise RuntimeError(f"Missing required tables: {', '.join(missing_tables)}")

    orders_columns = {col["name"] for col in inspector.get_columns("orders")}
    amount_column = "total_amount" if "total_amount" in orders_columns else None
    if amount_column is None and "total_price" in orders_columns:
        amount_column = "total_price"
    if amount_column is None:
        raise RuntimeError("orders table is missing both total_amount and total_price columns")

    return SchemaProfile(
        order_amount_column=amount_column,
        has_order_items="order_items" in table_names,
        has_reviews="reviews" in table_names,
        has_order_status="status" in orders_columns,
        has_promo_id="promo_id" in orders_columns,
    )


def _build_feature_sql(
    schema: SchemaProfile,
    *,
    include_label: bool,
    filter_single_user: bool,
) -> str:
    user_filter_sql = "WHERE u.id = :user_id" if filter_single_user else ""

    status_expr = (
        "CASE WHEN LOWER(COALESCE(o.status::text, '')) IN ('cancelled', 'failed') THEN 1 ELSE 0 END"
        if schema.has_order_status
        else "0"
    )
    promo_expr = "CASE WHEN o.promo_id IS NOT NULL THEN 1 ELSE 0 END" if schema.has_promo_id else "0"

    if schema.has_order_items:
        item_cte_sql = """
, per_order_items AS (
    SELECT
        oi.order_id,
        SUM(oi.quantity::double precision) AS items_per_order,
        COUNT(DISTINCT oi.product_id) AS distinct_products_per_order
    FROM order_items oi
    JOIN orders_lookback ol ON ol.id = oi.order_id
    GROUP BY oi.order_id
)
, item_features AS (
    SELECT
        ol.user_id,
        AVG(p.items_per_order) AS avg_items_per_order_lookback,
        AVG(p.distinct_products_per_order) AS avg_distinct_products_per_order_lookback
    FROM per_order_items p
    JOIN orders_lookback ol ON ol.id = p.order_id
    GROUP BY ol.user_id
)
"""
        item_join_sql = "LEFT JOIN item_features itf ON itf.user_id = bu.user_id"
        item_select_sql = """
, COALESCE(itf.avg_items_per_order_lookback, 0.0) AS avg_items_per_order_lookback
, COALESCE(itf.avg_distinct_products_per_order_lookback, 0.0) AS avg_distinct_products_per_order_lookback
"""
    else:
        item_cte_sql = ""
        item_join_sql = ""
        item_select_sql = """
, 0.0 AS avg_items_per_order_lookback
, 0.0 AS avg_distinct_products_per_order_lookback
"""

    if schema.has_reviews:
        review_cte_sql = """
, review_features AS (
    SELECT
        r.user_id,
        AVG(r.rating::double precision) AS avg_rating_lifetime,
        COUNT(*) AS review_count_lifetime
    FROM reviews r
    WHERE r.created_at < :snapshot_ts
    GROUP BY r.user_id
)
"""
        review_join_sql = "LEFT JOIN review_features rf ON rf.user_id = bu.user_id"
        review_select_sql = """
, COALESCE(rf.avg_rating_lifetime, 0.0) AS avg_rating_lifetime
, COALESCE(rf.review_count_lifetime, 0) AS review_count_lifetime
"""
    else:
        review_cte_sql = ""
        review_join_sql = ""
        review_select_sql = """
, 0.0 AS avg_rating_lifetime
, 0 AS review_count_lifetime
"""

    if include_label:
        label_cte_sql = """
, labels AS (
    SELECT
        bu.user_id,
        MAX(
            CASE
                WHEN o.created_at >= :snapshot_ts AND o.created_at < :label_end_ts THEN 1
                ELSE 0
            END
        )::int AS will_order_next_30d
    FROM base_users bu
    LEFT JOIN orders o ON o.user_id = bu.user_id
    GROUP BY bu.user_id
)
"""
        label_join_sql = "LEFT JOIN labels lbl ON lbl.user_id = bu.user_id"
        label_select_sql = ", COALESCE(lbl.will_order_next_30d, 0) AS will_order_next_30d"
    else:
        label_cte_sql = ""
        label_join_sql = ""
        label_select_sql = ""

    return f"""
WITH base_users AS (
    SELECT
        u.id AS user_id,
        u.created_at AS user_created_at
    FROM users u
    {user_filter_sql}
)
, orders_hist AS (
    SELECT
        o.id,
        o.user_id,
        o.created_at,
        o.{schema.order_amount_column}::double precision AS order_amount,
        {status_expr} AS is_cancelled,
        {promo_expr} AS used_promo
    FROM orders o
    JOIN base_users bu ON bu.user_id = o.user_id
    WHERE o.created_at < :snapshot_ts
)
, orders_lookback AS (
    SELECT *
    FROM orders_hist
    WHERE created_at >= :history_start_ts
)
, order_gaps AS (
    SELECT
        user_id,
        created_at,
        EXTRACT(EPOCH FROM (created_at - LAG(created_at) OVER (PARTITION BY user_id ORDER BY created_at)))
            / 86400.0 AS gap_days
    FROM orders_hist
)
, lookback_features AS (
    SELECT
        bu.user_id,
        COUNT(ol.id) AS orders_lookback,
        SUM(CASE WHEN ol.created_at >= :t30_start_ts THEN 1 ELSE 0 END) AS orders_30d,
        SUM(CASE WHEN ol.created_at >= :t60_start_ts THEN 1 ELSE 0 END) AS orders_60d,
        SUM(CASE WHEN ol.created_at >= :t90_start_ts THEN 1 ELSE 0 END) AS orders_90d,
        COALESCE(SUM(ol.order_amount), 0.0) AS revenue_lookback,
        AVG(ol.order_amount) AS avg_order_value_lookback,
        STDDEV_SAMP(ol.order_amount) AS std_order_value_lookback,
        AVG(CASE WHEN EXTRACT(ISODOW FROM ol.created_at) IN (6, 7) THEN 1.0 ELSE 0.0 END)
            AS weekend_order_ratio_lookback,
        AVG(CASE WHEN EXTRACT(HOUR FROM ol.created_at) BETWEEN 18 AND 21 THEN 1.0 ELSE 0.0 END)
            AS dinner_order_ratio_lookback,
        AVG(ol.is_cancelled::double precision) AS cancel_ratio_lookback,
        AVG(ol.used_promo::double precision) AS promo_order_ratio_lookback,
        EXTRACT(EPOCH FROM (:snapshot_ts - MAX(ol.created_at))) / 86400.0 AS days_since_last_order
    FROM base_users bu
    LEFT JOIN orders_lookback ol ON ol.user_id = bu.user_id
    GROUP BY bu.user_id
)
, lifetime_features AS (
    SELECT
        user_id,
        COUNT(*) AS order_count_lifetime,
        COALESCE(SUM(order_amount), 0.0) AS revenue_lifetime
    FROM orders_hist
    GROUP BY user_id
)
, gap_features AS (
    SELECT
        user_id,
        AVG(gap_days) AS avg_gap_days_lookback,
        STDDEV_SAMP(gap_days) AS std_gap_days_lookback,
        MAX(gap_days) AS max_gap_days_lookback
    FROM order_gaps
    WHERE created_at >= :history_start_ts
      AND gap_days IS NOT NULL
    GROUP BY user_id
)
{item_cte_sql}
{review_cte_sql}
{label_cte_sql}
SELECT
    bu.user_id,
    CAST(:snapshot_date AS date) AS snapshot_date,
    COALESCE(lf.orders_lookback, 0) AS orders_lookback,
    COALESCE(lf.orders_30d, 0) AS orders_30d,
    COALESCE(lf.orders_60d, 0) AS orders_60d,
    COALESCE(lf.orders_90d, 0) AS orders_90d,
    COALESCE(lf.revenue_lookback, 0.0) AS revenue_lookback,
    COALESCE(lf.avg_order_value_lookback, 0.0) AS avg_order_value_lookback,
    COALESCE(lf.std_order_value_lookback, 0.0) AS std_order_value_lookback,
    COALESCE(lf.weekend_order_ratio_lookback, 0.0) AS weekend_order_ratio_lookback,
    COALESCE(lf.dinner_order_ratio_lookback, 0.0) AS dinner_order_ratio_lookback,
    COALESCE(lf.cancel_ratio_lookback, 0.0) AS cancel_ratio_lookback,
    COALESCE(lf.promo_order_ratio_lookback, 0.0) AS promo_order_ratio_lookback,
    COALESCE(lf.days_since_last_order, 365.0) AS days_since_last_order,
    COALESCE(EXTRACT(EPOCH FROM (:snapshot_ts - bu.user_created_at)) / 86400.0, 0.0) AS customer_age_days,
    COALESCE(ltf.order_count_lifetime, 0) AS order_count_lifetime,
    COALESCE(ltf.revenue_lifetime, 0.0) AS revenue_lifetime,
    COALESCE(gf.avg_gap_days_lookback, 0.0) AS avg_gap_days_lookback,
    COALESCE(gf.std_gap_days_lookback, 0.0) AS std_gap_days_lookback,
    COALESCE(gf.max_gap_days_lookback, 0.0) AS max_gap_days_lookback
    {item_select_sql}
    {review_select_sql}
    {label_select_sql}
FROM base_users bu
LEFT JOIN lookback_features lf ON lf.user_id = bu.user_id
LEFT JOIN lifetime_features ltf ON ltf.user_id = bu.user_id
LEFT JOIN gap_features gf ON gf.user_id = bu.user_id
{item_join_sql}
{review_join_sql}
{label_join_sql}
WHERE COALESCE(ltf.order_count_lifetime, 0) > 0
ORDER BY bu.user_id;
"""


def fetch_churn_feature_rows(
    engine: Engine,
    *,
    snapshot_ts: datetime,
    history_days: int = DEFAULT_HISTORY_DAYS,
    label_days: int = DEFAULT_LABEL_DAYS,
    user_id: str | None = None,
    include_label: bool = False,
) -> list[dict[str, Any]]:
    profile = _profile_schema(engine)
    snapshot_ts_utc = _as_utc(snapshot_ts)

    sql = _build_feature_sql(
        profile,
        include_label=include_label,
        filter_single_user=user_id is not None,
    )
    query = text(sql)

    params: dict[str, Any] = {
        "snapshot_ts": snapshot_ts_utc,
        "snapshot_date": snapshot_ts_utc.date().isoformat(),
        "history_start_ts": snapshot_ts_utc - timedelta(days=history_days),
        "label_end_ts": snapshot_ts_utc + timedelta(days=label_days),
        "t30_start_ts": snapshot_ts_utc - timedelta(days=30),
        "t60_start_ts": snapshot_ts_utc - timedelta(days=60),
        "t90_start_ts": snapshot_ts_utc - timedelta(days=90),
    }
    if user_id is not None:
        params["user_id"] = user_id

    with engine.connect() as conn:
        rows = conn.execute(query, params).mappings().all()

    return [dict(row) for row in rows]


def fetch_churn_feature_frame(
    engine: Engine,
    *,
    snapshot_ts: datetime,
    history_days: int = DEFAULT_HISTORY_DAYS,
    label_days: int = DEFAULT_LABEL_DAYS,
    user_id: str | None = None,
    include_label: bool = False,
):
    import pandas as pd

    rows = fetch_churn_feature_rows(
        engine,
        snapshot_ts=snapshot_ts,
        history_days=history_days,
        label_days=label_days,
        user_id=user_id,
        include_label=include_label,
    )
    frame = pd.DataFrame(rows)
    if not frame.empty and "snapshot_date" in frame.columns:
        frame["snapshot_date"] = pd.to_datetime(frame["snapshot_date"], utc=True)
    return frame


def generate_snapshot_schedule(
    engine: Engine,
    *,
    history_days: int = DEFAULT_HISTORY_DAYS,
    label_days: int = DEFAULT_LABEL_DAYS,
    snapshots: int = 12,
    spacing_days: int = 14,
) -> list[datetime]:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT MIN(created_at) AS min_ts, MAX(created_at) AS max_ts FROM orders")
        ).mappings().one()

    min_ts = row["min_ts"]
    max_ts = row["max_ts"]
    if min_ts is None or max_ts is None:
        return []

    min_ts_utc = _as_utc(min_ts)
    max_ts_utc = _as_utc(max_ts)

    earliest_snapshot = min_ts_utc + timedelta(days=history_days)
    latest_snapshot = max_ts_utc - timedelta(days=label_days)
    if latest_snapshot < earliest_snapshot:
        return []

    cursor = latest_snapshot.replace(hour=0, minute=0, second=0, microsecond=0)
    schedule: list[datetime] = []
    while len(schedule) < snapshots and cursor >= earliest_snapshot:
        schedule.append(cursor)
        cursor -= timedelta(days=spacing_days)

    schedule.reverse()
    return schedule


def build_feature_vector(row: dict[str, Any], feature_names: list[str]) -> list[float]:
    vector: list[float] = []
    for name in feature_names:
        raw_value = row.get(name)
        if raw_value is None:
            vector.append(float("nan"))
            continue
        try:
            vector.append(float(raw_value))
        except (TypeError, ValueError):
            vector.append(float("nan"))
    return vector
