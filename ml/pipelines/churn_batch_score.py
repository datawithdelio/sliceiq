from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import inspect, text

from ml.pipelines.churn_common import (
    DEFAULT_HISTORY_DAYS,
    build_feature_vector,
    create_db_engine,
    fetch_churn_feature_rows,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch score SliceIQ users with the churn/reorder model."
    )
    parser.add_argument("--database-url", default=None, help="Override DATABASE_URL")
    parser.add_argument(
        "--model-path",
        default="ml/models/churn_reorder_model.joblib",
        help="Model artifact path from churn_train.py",
    )
    parser.add_argument(
        "--output",
        default="ml/data/churn_scoring_latest.csv",
        help="Output CSV path for scored users.",
    )
    parser.add_argument(
        "--history-days",
        type=int,
        default=DEFAULT_HISTORY_DAYS,
        help="Lookback window used for live scoring features.",
    )
    parser.add_argument(
        "--snapshot-ts",
        default=None,
        help="Optional ISO timestamp for backtesting (default: now UTC).",
    )
    parser.add_argument(
        "--write-predictions-table",
        action="store_true",
        help="Write scores to the predictions table if it exists.",
    )
    return parser.parse_args()


def risk_bucket(prob: float) -> str:
    churn_prob = 1.0 - prob
    if churn_prob >= 0.7:
        return "high"
    if churn_prob >= 0.4:
        return "medium"
    return "low"


def main() -> None:
    args = parse_args()

    model_path = Path(args.model_path)
    if not model_path.exists():
        raise FileNotFoundError(
            f"Model artifact missing at {model_path}. Run churn_train.py first."
        )
    artifact = joblib.load(model_path)
    model = artifact["model"]
    selected_features = artifact["selected_features"]
    threshold = float(artifact.get("threshold", 0.5))
    model_name = artifact.get("model_name", "sliceiq_reorder_propensity")
    model_version = artifact.get("model_version", "dev")

    snapshot_ts = (
        datetime.fromisoformat(args.snapshot_ts).astimezone(UTC)
        if args.snapshot_ts
        else datetime.now(UTC)
    )
    engine = create_db_engine(args.database_url)
    rows = fetch_churn_feature_rows(
        engine,
        snapshot_ts=snapshot_ts,
        history_days=args.history_days,
        include_label=False,
    )
    if not rows:
        raise RuntimeError("No users were eligible for scoring.")

    feature_matrix = np.array(
        [build_feature_vector(row, selected_features) for row in rows], dtype=float
    )
    reorder_prob = model.predict_proba(feature_matrix)[:, 1]

    scored = pd.DataFrame(
        {
            "user_id": [str(row["user_id"]) for row in rows],
            "snapshot_ts": snapshot_ts.isoformat(),
            "reorder_probability_30d": reorder_prob,
            "churn_probability_30d": 1.0 - reorder_prob,
            "recommended_threshold": threshold,
            "predicted_positive": (reorder_prob >= threshold).astype(int),
        }
    )
    scored["risk_bucket"] = scored["reorder_probability_30d"].map(risk_bucket)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    scored.to_csv(output_path, index=False)
    print(f"[done] scored_users={len(scored)} output={output_path}")

    if not args.write_predictions_table:
        return

    inspector = inspect(engine)
    if "predictions" not in set(inspector.get_table_names()):
        print("[warn] predictions table not found; skipping DB write.")
        return

    with engine.begin() as conn:
        for _, row in scored.iterrows():
            payload = {
                "reorder_probability_30d": float(row["reorder_probability_30d"]),
                "churn_probability_30d": float(row["churn_probability_30d"]),
                "risk_bucket": row["risk_bucket"],
                "threshold": threshold,
            }
            conn.execute(
                text(
                    """
                    INSERT INTO predictions (
                        model_name,
                        model_version,
                        entity_type,
                        entity_id,
                        prediction
                    )
                    VALUES (
                        :model_name,
                        :model_version,
                        'user',
                        :entity_id::uuid,
                        :prediction::jsonb
                    )
                    """
                ),
                {
                    "model_name": model_name,
                    "model_version": model_version,
                    "entity_id": row["user_id"],
                    "prediction": json.dumps(payload),
                },
            )
    print("[done] predictions table updated")


if __name__ == "__main__":
    main()

