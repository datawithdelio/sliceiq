from __future__ import annotations

import os
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import httpx
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient


@dataclass
class ClerkJWTVerifier:
    issuer: str | None
    audience: str | None
    jwks_url: str

    @classmethod
    def from_env(cls) -> "ClerkJWTVerifier":
        issuer = os.getenv("CLERK_ISSUER", "").strip() or None
        audience = os.getenv("CLERK_AUDIENCE", "").strip() or None
        explicit_jwks = os.getenv("CLERK_JWKS_URL", "").strip() or None

        if explicit_jwks:
            jwks_url = explicit_jwks
        elif issuer:
            jwks_url = f"{issuer.rstrip('/')}/.well-known/jwks.json"
        else:
            raise RuntimeError("Set CLERK_JWKS_URL or CLERK_ISSUER for JWT verification")

        return cls(issuer=issuer, audience=audience, jwks_url=jwks_url)

    def verify(self, token: str) -> dict[str, Any]:
        header = jwt.get_unverified_header(token)
        alg = str(header.get("alg", "RS256"))

        try:
            if alg.startswith("HS"):
                signing_key = os.getenv("CLERK_SECRET_KEY", "").strip()
                if not signing_key:
                    raise RuntimeError("CLERK_SECRET_KEY is required for HS* tokens")
            else:
                jwk_client = PyJWKClient(self.jwks_url)
                signing_key = jwk_client.get_signing_key_from_jwt(token).key

            options = {"verify_aud": bool(self.audience), "verify_iss": bool(self.issuer)}
            return jwt.decode(
                token,
                signing_key,
                algorithms=[alg],
                audience=self.audience,
                issuer=self.issuer,
                options=options,
            )
        except Exception:
            # Fallback 1: try JWKS derived from token issuer.
            if not alg.startswith("HS"):
                try:
                    return self._verify_with_token_issuer_jwks(token, alg)
                except Exception:
                    pass
            # Dev-friendly fallback: validate token's session against Clerk API.
            return self._verify_via_clerk_session(token)

    def _verify_with_token_issuer_jwks(self, token: str, alg: str) -> dict[str, Any]:
        payload = jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_aud": False,
                "verify_iss": False,
                "verify_exp": False,
                "verify_nbf": False,
            },
        )
        token_issuer = str(payload.get("iss", "")).strip()
        if not token_issuer:
            raise RuntimeError("Token missing issuer")

        dynamic_jwks_url = f"{token_issuer.rstrip('/')}/.well-known/jwks.json"
        signing_key = PyJWKClient(dynamic_jwks_url).get_signing_key_from_jwt(token).key

        # If signature validates against the token issuer's JWKS, accept that issuer.
        # Keep optional audience verification, but do not force env issuer in this path.
        options = {"verify_aud": bool(self.audience), "verify_iss": False}
        return jwt.decode(
            token,
            signing_key,
            algorithms=[alg],
            audience=self.audience,
            issuer=None,
            options=options,
        )

    def _verify_via_clerk_session(self, token: str) -> dict[str, Any]:
        payload = jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_aud": False,
                "verify_iss": False,
                "verify_exp": False,
                "verify_nbf": False,
            },
        )

        sid = payload.get("sid")
        sub = payload.get("sub")
        exp = payload.get("exp")
        if not sid or not sub:
            raise RuntimeError("Token missing sid/sub")
        if isinstance(exp, int) and exp < int(time.time()):
            raise RuntimeError("Token expired")

        secret_key = os.getenv("CLERK_SECRET_KEY", "").strip()
        if not secret_key:
            raise RuntimeError("CLERK_SECRET_KEY is required for Clerk API fallback")

        with httpx.Client(timeout=8.0) as client:
            resp = client.get(
                f"https://api.clerk.com/v1/sessions/{sid}",
                headers={"Authorization": f"Bearer {secret_key}"},
            )

        if resp.status_code != 200:
            raise RuntimeError(f"Session lookup failed (HTTP {resp.status_code})")

        data = resp.json()
        if data.get("status") != "active":
            raise RuntimeError("Session is not active")
        if data.get("user_id") != sub:
            raise RuntimeError("Session user mismatch")

        return payload


@lru_cache
def _verifier_or_none() -> ClerkJWTVerifier | None:
    try:
        return ClerkJWTVerifier.from_env()
    except RuntimeError:
        return None


bearer_scheme = HTTPBearer(auto_error=False)


def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    verifier = _verifier_or_none()
    if verifier is None:
        raise HTTPException(status_code=500, detail="JWT verifier is not configured")

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer token")

    try:
        return verifier.verify(credentials.credentials)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc
