from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path

import pandas as pd

from ml.pipelines.churn_common import (
    DEFAULT_HISTORY_DAYS,
    DEFAULT_LABEL_DAYS,
    create_db_engine,
    fetch_churn_feature_frame,
    generate_snapshot_schedule,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a point-in-time churn training dataset for SliceIQ."
    )
    parser.add_argument("--database-url", default=None, help="Override DATABASE_URL")
    parser.add_argument("--history-days", type=int, default=DEFAULT_HISTORY_DAYS)
    parser.add_argument("--label-days", type=int, default=DEFAULT_LABEL_DAYS)
    parser.add_argument("--snapshots", type=int, default=12)
    parser.add_argument("--spacing-days", type=int, default=14)
    parser.add_argument(
        "--output",
        default="ml/data/churn_training_dataset.csv",
        help="CSV output path for the training dataset.",
    )
    parser.add_argument(
        "--metadata-output",
        default="ml/data/churn_training_metadata.json",
        help="JSON output path for build metadata.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engine = create_db_engine(args.database_url)

    snapshots = generate_snapshot_schedule(
        engine,
        history_days=args.history_days,
        label_days=args.label_days,
        snapshots=args.snapshots,
        spacing_days=args.spacing_days,
    )
    if not snapshots:
        raise RuntimeError(
            "Could not generate snapshot schedule. Ensure orders exist with enough history."
        )

    frames: list[pd.DataFrame] = []
    for snapshot in snapshots:
        frame = fetch_churn_feature_frame(
            engine,
            snapshot_ts=snapshot,
            history_days=args.history_days,
            label_days=args.label_days,
            include_label=True,
        )
        if frame.empty:
            continue
        frames.append(frame)
        print(
            f"[build] snapshot={snapshot.date().isoformat()} rows={len(frame)} "
            f"positive_rate={frame['will_order_next_30d'].mean():.4f}"
        )

    if not frames:
        raise RuntimeError("No dataset rows were produced from any snapshot.")

    dataset = pd.concat(frames, ignore_index=True)
    dataset["snapshot_date"] = pd.to_datetime(dataset["snapshot_date"], utc=True)
    dataset["user_id"] = dataset["user_id"].astype(str)
    dataset = dataset.drop_duplicates(subset=["user_id", "snapshot_date"], keep="last")
    dataset = dataset.sort_values(["snapshot_date", "user_id"]).reset_index(drop=True)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(output_path, index=False)

    metadata = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "rows": int(len(dataset)),
        "snapshots": [dt.date().isoformat() for dt in sorted(dataset["snapshot_date"].unique())],
        "positive_rate": float(dataset["will_order_next_30d"].mean()),
        "history_days": int(args.history_days),
        "label_days": int(args.label_days),
        "snapshot_spacing_days": int(args.spacing_days),
        "columns": dataset.columns.tolist(),
    }
    metadata_path = Path(args.metadata_output)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"[done] dataset rows={len(dataset)} path={output_path}")
    print(f"[done] metadata path={metadata_path}")


if __name__ == "__main__":
    main()

