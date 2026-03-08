from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    address: Optional[dict] = None
    avatar_url: Optional[str] = None


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    role: str
    avatar_url: Optional[str]
    address: Optional[dict]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
