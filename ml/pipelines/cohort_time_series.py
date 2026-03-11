from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sqlalchemy import inspect, text

from ml.pipelines.churn_common import create_db_engine


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Advanced cohort and time-series analysis for SliceIQ orders."
    )
    parser.add_argument("--database-url", default=None, help="Override DATABASE_URL")
    parser.add_argument("--output-dir", default="ml/data/reports/causal/cohort_time_series")
    return parser.parse_args()


def _resolve_amount_column(engine) -> str:
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("orders")}
    if "total_amount" in columns:
        return "total_amount"
    if "total_price" in columns:
        return "total_price"
    raise RuntimeError("orders table missing total_amount/total_price")


def _load_orders(engine, amount_col: str) -> pd.DataFrame:
    query = text(
        f"""
        SELECT
            user_id::text AS user_id,
            created_at,
            {amount_col}::double precision AS order_amount
        FROM orders
        WHERE created_at IS NOT NULL
        """
    )
    df = pd.read_sql(query, engine)
    if df.empty:
        return df
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
    df["order_amount"] = pd.to_numeric(df["order_amount"], errors="coerce").fillna(0.0)
    return df


def _build_cohort_tables(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = df.copy()
    work["order_month"] = work["created_at"].dt.to_period("M").dt.to_timestamp()
    first_order = (
        work.groupby("user_id", as_index=False)["order_month"]
        .min()
        .rename(columns={"order_month": "cohort_month"})
    )
    work = work.merge(first_order, on="user_id", how="left")

    work["period"] = (
        (work["order_month"].dt.year - work["cohort_month"].dt.year) * 12
        + (work["order_month"].dt.month - work["cohort_month"].dt.month)
    ).astype(int)

    cohort_metrics = (
        work.groupby(["cohort_month", "period"], as_index=False)
        .agg(
            active_users=("user_id", "nunique"),
            orders=("user_id", "size"),
            revenue=("order_amount", "sum"),
        )
        .sort_values(["cohort_month", "period"])
    )

    cohort_size = (
        cohort_metrics[cohort_metrics["period"] == 0][["cohort_month", "active_users", "revenue"]]
        .rename(columns={"active_users": "cohort_size", "revenue": "cohort_rev0"})
    )
    cohort_metrics = cohort_metrics.merge(cohort_size, on="cohort_month", how="left")
    cohort_metrics["retention_rate"] = (
        cohort_metrics["active_users"] / cohort_metrics["cohort_size"].replace(0, np.nan)
    ).fillna(0.0)
    cohort_metrics["revenue_retention_rate"] = (
        cohort_metrics["revenue"] / cohort_metrics["cohort_rev0"].replace(0, np.nan)
    ).fillna(0.0)

    retention_pivot = cohort_metrics.pivot(
        index="cohort_month", columns="period", values="retention_rate"
    ).fillna(0.0)
    return cohort_metrics, retention_pivot


def _build_daily_timeseries(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work["order_day"] = work["created_at"].dt.floor("D")
    daily = (
        work.groupby("order_day", as_index=False)
        .agg(
            orders=("user_id", "size"),
            revenue=("order_amount", "sum"),
            unique_users=("user_id", "nunique"),
        )
        .sort_values("order_day")
    )
    if daily.empty:
        return daily

    full_days = pd.date_range(
        start=daily["order_day"].min(),
        end=daily["order_day"].max(),
        freq="D",
        tz="UTC",
    )
    daily = daily.set_index("order_day").reindex(full_days, fill_value=0).reset_index()
    daily = daily.rename(columns={"index": "order_day"})

    daily["orders_7d_ma"] = daily["orders"].rolling(window=7, min_periods=2).mean()
    daily["orders_28d_ma"] = daily["orders"].rolling(window=28, min_periods=7).mean()
    daily["orders_28d_std"] = daily["orders"].rolling(window=28, min_periods=7).std().fillna(0.0)
    daily["orders_zscore"] = (
        (daily["orders"] - daily["orders_28d_ma"]) / daily["orders_28d_std"].replace(0, np.nan)
    ).fillna(0.0)
    daily["is_order_anomaly"] = daily["orders_zscore"].abs() >= 2.5

    if len(daily) >= 370:
        daily["orders_yoy"] = daily["orders"].shift(364)
        daily["orders_yoy_growth"] = (
            (daily["orders"] - daily["orders_yoy"]) / daily["orders_yoy"].replace(0, np.nan)
        ).fillna(0.0)
    else:
        daily["orders_yoy"] = np.nan
        daily["orders_yoy_growth"] = np.nan

    return daily


def _plot_retention_heatmap(pivot: pd.DataFrame, output_path: Path) -> None:
    if pivot.empty:
        return
    fig, ax = plt.subplots(figsize=(11, 6))
    heatmap = ax.imshow(pivot.values, aspect="auto", cmap="YlGnBu", vmin=0.0, vmax=1.0)
    ax.set_title("Cohort Retention Heatmap")
    ax.set_xlabel("Period (months since first order)")
    ax.set_ylabel("Cohort Month")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([pd.Timestamp(i).strftime("%Y-%m") for i in pivot.index])
    fig.colorbar(heatmap, ax=ax, label="Retention Rate")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def _plot_daily_series(daily: pd.DataFrame, output_path: Path) -> None:
    if daily.empty:
        return
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(daily["order_day"], daily["orders"], label="daily_orders", alpha=0.35)
    ax.plot(daily["order_day"], daily["orders_7d_ma"], label="orders_7d_ma", linewidth=2.0)
    ax.plot(daily["order_day"], daily["orders_28d_ma"], label="orders_28d_ma", linewidth=2.0)

    anomalies = daily[daily["is_order_anomaly"]]
    if not anomalies.empty:
        ax.scatter(
            anomalies["order_day"],
            anomalies["orders"],
            color="red",
            s=16,
            label="anomaly(|z|>=2.5)",
            zorder=3,
        )

    ax.set_title("Order Time Series with Rolling Windows and Anomalies")
    ax.set_xlabel("Day")
    ax.set_ylabel("Order Count")
    ax.grid(alpha=0.2)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def _write_report(
    *,
    output_path: Path,
    cohort_metrics: pd.DataFrame,
    daily: pd.DataFrame,
) -> None:
    cohort_count = cohort_metrics["cohort_month"].nunique() if not cohort_metrics.empty else 0
    max_period = int(cohort_metrics["period"].max()) if not cohort_metrics.empty else 0
    anomalies = int(daily["is_order_anomaly"].sum()) if not daily.empty else 0
    mean_retention_p1 = (
        cohort_metrics[cohort_metrics["period"] == 1]["retention_rate"].mean()
        if not cohort_metrics.empty and (cohort_metrics["period"] == 1).any()
        else np.nan
    )

    lines = [
        "# SliceIQ Cohort + Time-Series Report",
        "",
        f"- Generated at (UTC): {datetime.now(UTC).isoformat()}",
        f"- Cohort count: {cohort_count}",
        f"- Max observed cohort period: {max_period}",
        f"- Mean period-1 retention: {mean_retention_p1 if pd.notna(mean_retention_p1) else 'n/a'}",
        f"- Daily order anomalies (|z| >= 2.5): {anomalies}",
        "",
        "## Recommended Follow-Ups",
        "- Compare retention/revenue retention by promo usage or category.",
        "- Use anomalies to annotate campaigns, outages, or holidays.",
        "- Feed cohort period features into downstream churn/uplift models.",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    engine = create_db_engine(args.database_url)
    amount_col = _resolve_amount_column(engine)
    orders = _load_orders(engine, amount_col)
    if orders.empty:
        raise RuntimeError("No orders found for cohort/time-series analysis.")

    cohort_metrics, retention_pivot = _build_cohort_tables(orders)
    daily = _build_daily_timeseries(orders)

    cohort_metrics.to_csv(output_dir / "cohort_metrics.csv", index=False)
    retention_pivot.to_csv(output_dir / "cohort_retention_matrix.csv")
    daily.to_csv(output_dir / "daily_timeseries_metrics.csv", index=False)

    _plot_retention_heatmap(retention_pivot, output_dir / "cohort_retention_heatmap.png")
    _plot_daily_series(daily, output_dir / "daily_orders_timeseries.png")
    _write_report(
        output_path=output_dir / "cohort_time_series_report.md",
        cohort_metrics=cohort_metrics,
        daily=daily,
    )

    print(f"[done] Cohort/time-series report generated at {output_dir}")


if __name__ == "__main__":
    main()

