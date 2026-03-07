from typing import Any

from fastapi import APIRouter, Depends

from app.auth import require_auth

router = APIRouter(prefix="/protected", tags=["protected"])


@router.get("/me")
async def protected_me(payload: dict[str, Any] = Depends(require_auth)) -> dict[str, str]:
    return {
        "status": "ok",
        "user_id": payload.get("sub", ""),
    }
