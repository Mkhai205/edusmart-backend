import uuid

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.security import TokenError, decode_token
from src.infrastructure.database.session import get_db_session
from src.infrastructure.storage.minio_client import MinioStorageClient
from src.modules.auth.service import AuthService

settings = get_settings()
minio_client = MinioStorageClient()


async def get_current_user_id(
    access_token: str | None = Cookie(default=None, alias=settings.access_cookie_name),
) -> uuid.UUID:
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing access token")

    try:
        payload = decode_token(access_token, expected_type="access")
        return uuid.UUID(payload["sub"])
    except (TokenError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from exc


async def get_current_user(
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    service = AuthService(session)
    return await service.get_user(user_id)


def get_minio_client() -> MinioStorageClient:
    return minio_client
