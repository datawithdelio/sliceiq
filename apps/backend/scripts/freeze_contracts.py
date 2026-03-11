from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.append(str(BACKEND_ROOT))

from app.main import app  # noqa: E402
from app.schemas.order import OrderCreate, OrderResponse, OrderStatusUpdate  # noqa: E402
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate  # noqa: E402
from app.schemas.user import UserResponse, UserUpdate  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = REPO_ROOT / "docs" / "api"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


OPENAPI_PATH = OUTPUT_DIR / "openapi.v1.json"
SCHEMAS_PATH = OUTPUT_DIR / "critical_schemas.v1.json"


openapi = app.openapi()
_write_json(OPENAPI_PATH, openapi)


churn_score_schema = {
    "title": "ChurnScoreResponse",
    "type": "object",
    "properties": {
        "user_id": {"type": "string", "format": "uuid"},
        "model_name": {"type": "string"},
        "model_version": {"type": "string"},
        "reorder_probability_30d": {"type": "number"},
        "churn_probability_30d": {"type": "number"},
        "threshold": {"type": "number"},
        "predicted_reorder_positive": {"type": "boolean"},
        "risk_bucket": {"type": "string", "enum": ["high", "medium", "low"]},
        "scored_at_utc": {"type": "string", "format": "date-time"},
        "prediction_saved": {"type": "boolean"},
    },
    "required": [
        "user_id",
        "model_name",
        "model_version",
        "reorder_probability_30d",
        "churn_probability_30d",
        "threshold",
        "predicted_reorder_positive",
        "risk_bucket",
        "scored_at_utc",
        "prediction_saved",
    ],
}

schemas = {
    "OrderCreate": OrderCreate.model_json_schema(),
    "OrderResponse": OrderResponse.model_json_schema(),
    "OrderStatusUpdate": OrderStatusUpdate.model_json_schema(),
    "UserUpdate": UserUpdate.model_json_schema(),
    "UserResponse": UserResponse.model_json_schema(),
    "ProductCreate": ProductCreate.model_json_schema(),
    "ProductUpdate": ProductUpdate.model_json_schema(),
    "ProductResponse": ProductResponse.model_json_schema(),
    "ChurnScoreResponse": churn_score_schema,
}

_write_json(SCHEMAS_PATH, schemas)
