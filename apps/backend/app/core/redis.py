from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from fastapi import HTTPException
from redis.asyncio import Redis


def _redis_url() -> str:
    # Upstash URL is preferred. Local REDIS_URL is a fallback for local Docker dev.
    url = os.getenv("UPSTASH_REDIS_URL", "").strip() or os.getenv("REDIS_URL", "").strip()
    if not url:
        raise HTTPException(status_code=500, detail="UPSTASH_REDIS_URL or REDIS_URL is not configured")
    return url


async def get_redis() -> AsyncGenerator[Redis, None]:
    client = Redis.from_url(_redis_url(), decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()
