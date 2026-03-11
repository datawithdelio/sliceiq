from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import json
import os
from pathlib import Path
import sys
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_admin
from app.models import User

router = APIRouter(prefix="/ml", tags=["ml"])


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))


def _model_path() -> Path:
    return Path(
        os.getenv(
            "CHURN_MODEL_PATH",
            str(REPO_ROOT / "ml" / "models" / "churn_reorder_model.joblib"),
        )
    )


def _to_risk_bucket(reorder_probability: float) -> str:
    churn_probability = 1.0 - reorder_probability
    if churn_probability >= 0.7:
        return "high"
    if churn_probability >= 0.4:
        return "medium"
    return "low"


@lru_cache(maxsize=1)
def _load_artifact(model_path: str) -> dict[str, Any]:
    import joblib

    return joblib.load(model_path)


def _save_prediction(
    db: Session,
    *,
    user_id: UUID,
    model_name: str,
    model_version: str,
    payload: dict[str, Any],
) -> bool:
    try:
        db.execute(
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
                "entity_id": str(user_id),
                "prediction": json.dumps(payload),
            },
        )
        db.commit()
        return True
    except SQLAlchemyError:
        db.rollback()
        return False


@router.get("/churn/{user_id}")
def score_user_churn(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict[str, Any]:
    _ = admin
    path = _model_path()
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Model artifact not found at {path}. Train and deploy the model first.",
        )

    try:
        from ml.pipelines.churn_common import build_feature_vector, fetch_churn_feature_rows
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to import ML feature module: {exc}") from exc

    try:
        artifact = _load_artifact(str(path))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load model artifact: {exc}") from exc

    selected_features = artifact.get("selected_features")
    model = artifact.get("model")
    if not isinstance(selected_features, list) or model is None:
        raise HTTPException(status_code=500, detail="Model artifact is missing required keys.")

    snapshot_ts = datetime.now(timezone.utc)
    history_days = int(os.getenv("CHURN_FEATURE_HISTORY_DAYS", "180"))
    rows = fetch_churn_feature_rows(
        db.get_bind(),
        snapshot_ts=snapshot_ts,
        history_days=history_days,
        user_id=str(user_id),
        include_label=False,
    )
    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No eligible feature row found for user (likely no historical orders).",
        )
    feature_row = rows[0]
    vector = [build_feature_vector(feature_row, selected_features)]

    try:
        reorder_probability = float(model.predict_proba(vector)[0][1])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Model prediction failed: {exc}") from exc

    threshold = float(artifact.get("threshold", 0.5))
    churn_probability = 1.0 - reorder_probability
    risk_bucket = _to_risk_bucket(reorder_probability)
    model_name = str(artifact.get("model_name", "sliceiq_reorder_propensity"))
    model_version = str(artifact.get("model_version", "dev"))

    prediction_payload = {
        "reorder_probability_30d": reorder_probability,
        "churn_probability_30d": churn_probability,
        "threshold": threshold,
        "risk_bucket": risk_bucket,
        "scored_at_utc": snapshot_ts.isoformat(),
    }
    saved = _save_prediction(
        db,
        user_id=user_id,
        model_name=model_name,
        model_version=model_version,
        payload=prediction_payload,
    )

    return {
        "user_id": str(user_id),
        "model_name": model_name,
        "model_version": model_version,
        "reorder_probability_30d": round(reorder_probability, 6),
        "churn_probability_30d": round(churn_probability, 6),
        "threshold": threshold,
        "predicted_reorder_positive": reorder_probability >= threshold,
        "risk_bucket": risk_bucket,
        "scored_at_utc": snapshot_ts.isoformat(),
        "prediction_saved": saved,
    }
