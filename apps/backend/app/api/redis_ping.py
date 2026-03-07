from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from redis.asyncio import Redis

from app.core.redis import get_redis

router = APIRouter(tags=["redis"])


@router.get("/ping-redis")
async def ping_redis(redis: Redis = Depends(get_redis)) -> dict[str, str]:
    key = "sliceiq:ping"
    value = datetime.now(UTC).isoformat()

    await redis.set(key, value, ex=60)
    stored = await redis.get(key)

    return {
        "status": "ok",
        "redis": "connected",
        "key": key,
        "value": stored or "",
    }

