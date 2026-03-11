from __future__ import annotations

import os
from typing import Optional

import socketio

from app.api.deps import _verify_token


def _allowed_origins() -> list[str]:
    origins = os.getenv("FRONTEND_ORIGINS", os.getenv("FRONTEND_URL", "http://localhost:3000"))
    return [origin.strip().rstrip("/") for origin in origins.split(",") if origin.strip()]


class SocketManager:
    def __init__(self) -> None:
        self.sio = socketio.AsyncServer(
            async_mode="asgi",
            cors_allowed_origins=_allowed_origins(),
        )
        self.app = socketio.ASGIApp(self.sio)

        @self.sio.event
        async def connect(sid, environ, auth=None):  # type: ignore[no-redef]
            token = None
            if isinstance(auth, dict):
                token = auth.get("token")
            if not token:
                return False

            try:
                payload = _verify_token(token)
            except Exception:
                return False

            user_id = payload.get("sub")
            if not user_id:
                return False

            await self.sio.enter_room(sid, str(user_id))
            print(f"User {user_id} connected to socket and joined private room.")

            metadata = payload.get("public_metadata") or {}
            role = None
            if isinstance(metadata, dict):
                role = metadata.get("role")
            role = role or payload.get("role") or payload.get("org_role")

            if role == "admin":
                await self.sio.enter_room(sid, "admin_room")

    async def emit_order_update(self, user_id: str, data: dict) -> None:
        await self.sio.emit(
            "order_status_update",
            data,
            room=str(user_id),
        )


socket_manager = SocketManager()
socket_app = socket_manager.app
