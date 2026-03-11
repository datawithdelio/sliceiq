from __future__ import annotations

import os
import time
from typing import Optional

import httpx
from fastapi import Header, HTTPException
from jose import jwt

_JWKS_CACHE: dict = {}
_JWKS_CACHE_TS: float = 0.0
_JWKS_TTL_SECONDS = 300


def _jwks_url() -> str:
    jwks_url = os.getenv("CLERK_JWKS_URL", "").strip()
    if not jwks_url:
        raise HTTPException(status_code=500, detail="CLERK_JWKS_URL is not configured")
    return jwks_url


def _issuer() -> str:
    issuer = os.getenv("CLERK_ISSUER_URL", "").strip()
    if not issuer:
        raise HTTPException(status_code=500, detail="CLERK_ISSUER_URL is not configured")
    return issuer


def _audience() -> Optional[str]:
    audience = os.getenv("CLERK_AUDIENCE", "").strip()
    return audience or None


def _fetch_jwks() -> dict:
    global _JWKS_CACHE, _JWKS_CACHE_TS
    now = time.time()
    if _JWKS_CACHE and (now - _JWKS_CACHE_TS) < _JWKS_TTL_SECONDS:
        return _JWKS_CACHE

    url = _jwks_url()
    try:
        resp = httpx.get(url, timeout=8.0)
        resp.raise_for_status()
        _JWKS_CACHE = resp.json()
        _JWKS_CACHE_TS = now
        return _JWKS_CACHE
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Failed to fetch JWKS: {exc}") from exc


def _verify_token(token: str) -> dict:
    try:
        unverified_header = jwt.get_unverified_header(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token header: {exc}") from exc

    kid = unverified_header.get("kid")
    alg = unverified_header.get("alg", "RS256")

    jwks = _fetch_jwks()
    keys = jwks.get("keys", [])
    key = next((k for k in keys if k.get("kid") == kid), None)
    if not key:
        raise HTTPException(status_code=401, detail="Invalid token key")

    issuer = _issuer()
    audience = _audience()

    try:
        return jwt.decode(
            token,
            key,
            algorithms=[alg],
            issuer=issuer,
            audience=audience,
            options={"verify_aud": bool(audience)},
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc


class JWTBearer:
    def __call__(self, authorization: Optional[str] = Header(default=None)) -> str:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Missing bearer token")

        token = authorization.split(" ", 1)[1].strip()
        if not token:
            raise HTTPException(status_code=401, detail="Missing bearer token")

        payload = _verify_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token subject")

        return str(user_id)


def get_current_user(authorization: Optional[str] = Header(default=None)) -> str:
    return JWTBearer()(authorization)
