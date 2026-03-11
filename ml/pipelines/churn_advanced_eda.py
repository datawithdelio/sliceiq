from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run advanced EDA on the churn training dataset."
    )
    parser.add_argument(
        "--input",
        default="ml/data/churn_training_dataset.csv",
        help="Input dataset from churn_build_dataset.py",
    )
    parser.add_argument(
        "--output-dir",
        default="ml/data/reports/churn",
        help="Directory where EDA outputs are written.",
    )
    return parser.parse_args()


def compute_snapshot_metrics(df: pd.DataFrame) -> pd.DataFrame:
    metrics = (
        df.groupby("snapshot_date", as_index=False)
        .agg(
            users=("user_id", "nunique"),
            target_rate=("will_order_next_30d", "mean"),
            avg_orders_30d=("orders_30d", "mean"),
            avg_revenue_lookback=("revenue_lookback", "mean"),
        )
        .sort_values("snapshot_date")
        .reset_index(drop=True)
    )
    metrics["orders_roll_mean_3"] = metrics["avg_orders_30d"].rolling(window=3, min_periods=2).mean()
    metrics["orders_roll_std_3"] = (
        metrics["avg_orders_30d"].rolling(window=3, min_periods=2).std().fillna(0.0)
    )
    metrics["orders_zscore"] = (
        (metrics["avg_orders_30d"] - metrics["orders_roll_mean_3"])
        / metrics["orders_roll_std_3"].replace(0, pd.NA)
    ).fillna(0.0)
    metrics["orders_is_anomaly"] = metrics["orders_zscore"].abs() >= 2.0
    return metrics


def compute_missingness(df: pd.DataFrame) -> pd.DataFrame:
    missing = (
        df.isna()
        .mean()
        .sort_values(ascending=False)
        .reset_index()
        .rename(columns={"index": "feature", 0: "missing_ratio"})
    )
    missing["missing_pct"] = (missing["missing_ratio"] * 100.0).round(2)
    return missing


def compute_correlations(df: pd.DataFrame) -> pd.DataFrame:
    numeric_columns = [
        col
        for col in df.columns
        if col not in {"will_order_next_30d"}
        and pd.api.types.is_numeric_dtype(df[col])
    ]
    corr_rows: list[dict[str, float | str]] = []
    for col in numeric_columns:
        corr = df[col].corr(df["will_order_next_30d"])
        corr_rows.append(
            {
                "feature": col,
                "corr_with_target": float(corr) if pd.notna(corr) else 0.0,
                "abs_corr": abs(float(corr)) if pd.notna(corr) else 0.0,
            }
        )
    corr_df = pd.DataFrame(corr_rows).sort_values("abs_corr", ascending=False).reset_index(drop=True)
    return corr_df


def compute_cohort_retention(df: pd.DataFrame) -> pd.DataFrame:
    slim = df[["user_id", "snapshot_date", "orders_30d"]].copy()
    slim["snapshot_key"] = slim["snapshot_date"].dt.strftime("%Y-%m-%d")
    first_seen = slim.groupby("user_id", as_index=False)["snapshot_key"].min().rename(
        columns={"snapshot_key": "cohort_key"}
    )
    slim = slim.merge(first_seen, on="user_id", how="left")

    ordered_snapshots = sorted(slim["snapshot_key"].unique().tolist())
    snapshot_index = {key: i for i, key in enumerate(ordered_snapshots)}
    slim["period"] = slim["snapshot_key"].map(snapshot_index) - slim["cohort_key"].map(snapshot_index)

    cohort_sizes = (
        slim[slim["period"] == 0]
        .groupby("cohort_key", as_index=False)["user_id"]
        .nunique()
        .rename(columns={"user_id": "cohort_size"})
    )
    active = (
        slim[slim["orders_30d"] > 0]
        .groupby(["cohort_key", "period"], as_index=False)["user_id"]
        .nunique()
        .rename(columns={"user_id": "active_users"})
    )
    retention = active.merge(cohort_sizes, on="cohort_key", how="left")
    retention["retention_rate"] = (
        retention["active_users"] / retention["cohort_size"].replace(0, pd.NA)
    ).fillna(0.0)
    return retention.sort_values(["cohort_key", "period"]).reset_index(drop=True)


def compute_gap_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    candidates = df[
        (df["order_count_lifetime"] >= 3)
        & (df["avg_gap_days_lookback"] > 0)
    ].copy()
    if candidates.empty:
        return pd.DataFrame(
            columns=[
                "user_id",
                "snapshot_date",
                "days_since_last_order",
                "avg_gap_days_lookback",
                "gap_multiplier",
            ]
        )

    candidates["gap_multiplier"] = (
        candidates["days_since_last_order"] / candidates["avg_gap_days_lookback"]
    )
    flagged = candidates[candidates["gap_multiplier"] >= 2.0].copy()
    flagged = flagged.sort_values("gap_multiplier", ascending=False)
    return flagged[
        [
            "user_id",
            "snapshot_date",
            "days_since_last_order",
            "avg_gap_days_lookback",
            "gap_multiplier",
        ]
    ]


def write_line_plot(snapshot_metrics: pd.DataFrame, output_dir: Path) -> None:
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(snapshot_metrics["snapshot_date"], snapshot_metrics["target_rate"], label="Target Rate")
    ax1.set_ylabel("Target Rate")
    ax1.set_xlabel("Snapshot Date")
    ax1.grid(alpha=0.25)

    ax2 = ax1.twinx()
    ax2.plot(
        snapshot_metrics["snapshot_date"],
        snapshot_metrics["avg_orders_30d"],
        color="tab:orange",
        label="Avg Orders 30d",
    )
    ax2.set_ylabel("Avg Orders (30d)")

    ax1.set_title("Reorder Propensity and Demand Trend by Snapshot")
    fig.tight_layout()
    fig.savefig(output_dir / "snapshot_trends.png", dpi=150)
    plt.close(fig)


def write_retention_heatmap(retention: pd.DataFrame, output_dir: Path) -> None:
    if retention.empty:
        return

    pivot = retention.pivot(index="cohort_key", columns="period", values="retention_rate").fillna(0.0)
    fig, ax = plt.subplots(figsize=(10, 6))
    heatmap = ax.imshow(pivot.values, aspect="auto", cmap="YlGnBu", vmin=0.0, vmax=1.0)
    ax.set_title("Cohort Retention Heatmap (Active in 30d Window)")
    ax.set_xlabel("Period Index")
    ax.set_ylabel("Cohort Snapshot")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    fig.colorbar(heatmap, ax=ax, label="Retention Rate")
    fig.tight_layout()
    fig.savefig(output_dir / "cohort_retention_heatmap.png", dpi=150)
    plt.close(fig)


def write_markdown_report(
    *,
    df: pd.DataFrame,
    snapshot_metrics: pd.DataFrame,
    missingness: pd.DataFrame,
    correlations: pd.DataFrame,
    retention: pd.DataFrame,
    gap_anomalies: pd.DataFrame,
    output_path: Path,
) -> None:
    total_rows = len(df)
    total_users = df["user_id"].nunique()
    total_snapshots = df["snapshot_date"].nunique()
    positive_rate = df["will_order_next_30d"].mean()
    anomaly_count = int(snapshot_metrics["orders_is_anomaly"].sum())
    gap_anomaly_users = gap_anomalies["user_id"].nunique()

    lines = [
        "# SliceIQ Churn Dataset - Advanced EDA Report",
        "",
        f"- Generated at (UTC): {datetime.now(UTC).isoformat()}",
        f"- Rows: {total_rows}",
        f"- Unique users: {total_users}",
        f"- Snapshot count: {total_snapshots}",
        f"- Positive class rate (`will_order_next_30d`): {positive_rate:.4f}",
        "",
        "## Time-Series and Anomaly Overview",
        f"- Snapshot-level demand anomalies (`|z| >= 2`): {anomaly_count}",
        f"- User-level gap anomalies (`days_since_last_order >= 2x avg_gap`): {gap_anomaly_users}",
        "",
        "## Top Target Correlations (absolute)",
    ]

    top_corr = correlations.head(12)[["feature", "corr_with_target"]]
    if top_corr.empty:
        lines.append("- No numeric correlations computed.")
    else:
        for _, row in top_corr.iterrows():
            lines.append(f"- `{row['feature']}`: {row['corr_with_target']:.4f}")

    lines.extend(["", "## Highest Missingness Features"])
    top_missing = missingness.head(12)[["feature", "missing_pct"]]
    for _, row in top_missing.iterrows():
        lines.append(f"- `{row['feature']}`: {row['missing_pct']:.2f}%")

    lines.extend(["", "## Cohort Retention Notes"])
    if retention.empty:
        lines.append("- Retention matrix is empty.")
    else:
        last_period = int(retention["period"].max())
        recent = retention[retention["period"] == last_period]
        mean_retention = recent["retention_rate"].mean()
        lines.append(f"- Max observed period index: {last_period}")
        lines.append(f"- Mean retention at max period: {mean_retention:.4f}")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(
            f"Input dataset does not exist at {input_path}. "
            "Run churn_build_dataset.py first."
        )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_path)
    required = {"user_id", "snapshot_date", "will_order_next_30d"}
    missing_required = required - set(df.columns)
    if missing_required:
        raise RuntimeError(f"Missing required dataset columns: {sorted(missing_required)}")

    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"], utc=True)
    df["will_order_next_30d"] = df["will_order_next_30d"].astype(int)

    snapshot_metrics = compute_snapshot_metrics(df)
    missingness = compute_missingness(df)
    correlations = compute_correlations(df)
    retention = compute_cohort_retention(df)
    gap_anomalies = compute_gap_anomalies(df)

    snapshot_metrics.to_csv(output_dir / "snapshot_metrics.csv", index=False)
    missingness.to_csv(output_dir / "missingness.csv", index=False)
    correlations.to_csv(output_dir / "feature_target_correlations.csv", index=False)
    retention.to_csv(output_dir / "cohort_retention.csv", index=False)
    gap_anomalies.to_csv(output_dir / "gap_anomalies.csv", index=False)

    write_line_plot(snapshot_metrics, output_dir)
    write_retention_heatmap(retention, output_dir)
    write_markdown_report(
        df=df,
        snapshot_metrics=snapshot_metrics,
        missingness=missingness,
        correlations=correlations,
        retention=retention,
        gap_anomalies=gap_anomalies,
        output_path=output_dir / "eda_report.md",
    )

    print(f"[done] Advanced EDA artifacts written to {output_dir}")


if __name__ == "__main__":
    main()

