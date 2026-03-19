from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status
from google.auth.transport import requests
from google.oauth2 import id_token

from src.core.config import get_settings
from src.modules.auth.schemas import GoogleProfile

settings = get_settings()
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


class GoogleOAuthClient:
    def build_login_url(self, state: str) -> str:
        query = {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(query)}"

    async def exchange_code(self, code: str) -> dict:
        payload = {
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect_uri,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(GOOGLE_TOKEN_URL, data=payload)

        if response.status_code >= 400:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Failed to exchange Google code")

        return response.json()

    async def get_profile(self, token_response: dict) -> GoogleProfile:
        raw_id_token = token_response.get("id_token")
        if raw_id_token:
            try:
                claims = id_token.verify_oauth2_token(
                    raw_id_token,
                    requests.Request(),
                    settings.google_client_id,
                )
                return GoogleProfile(
                    google_id=claims["sub"],
                    email=claims["email"],
                    full_name=claims.get("name"),
                    avatar_url=claims.get("picture"),
                )
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid Google ID token",
                ) from exc

        access_token = token_response.get("access_token")
        if not access_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Google access token")

        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(GOOGLE_USERINFO_URL, headers=headers)

        if response.status_code >= 400:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unable to fetch Google profile")

        profile = response.json()
        return GoogleProfile(
            google_id=profile["sub"],
            email=profile["email"],
            full_name=profile.get("name"),
            avatar_url=profile.get("picture"),
        )
