import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, HttpUrl


class GoogleProfile(BaseModel):
    google_id: str
    email: EmailStr
    full_name: str | None = None
    avatar_url: HttpUrl | None = None


class AuthUserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    avatar_url: HttpUrl | None = None


class AuthTokens(BaseModel):
    access_token: str
    refresh_token: str
    refresh_expires_at: datetime


class RefreshRequest(BaseModel):
    refresh_token: str | None = None
