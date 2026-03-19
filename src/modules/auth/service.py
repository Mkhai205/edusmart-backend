import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import TokenError, create_access_token, create_refresh_token, decode_token, hash_token
from src.modules.auth.repository import AuthRepository
from src.modules.auth.schemas import AuthTokens, GoogleProfile


class AuthService:
    def __init__(self, session: AsyncSession):
        self.repo = AuthRepository(session)
        self.session = session

    async def login_with_google(self, profile: GoogleProfile) -> tuple[uuid.UUID, AuthTokens]:
        user = await self.repo.create_or_update_google_user(profile)
        access_token = create_access_token(user_id=user.id)
        refresh_token, refresh_hash, refresh_expires_at, _ = create_refresh_token(user_id=user.id)
        await self.repo.store_refresh_token(
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=refresh_expires_at,
        )
        await self.session.commit()
        return user.id, AuthTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            refresh_expires_at=refresh_expires_at,
        )

    async def refresh(self, refresh_token: str) -> tuple[uuid.UUID, AuthTokens]:
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
        except TokenError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc

        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        token_hash = hash_token(refresh_token)
        record = await self.repo.find_valid_refresh_token(token_hash)
        if record is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked or expired")

        user_uuid = uuid.UUID(user_id)
        new_access = create_access_token(user_id=user_uuid)
        new_refresh, new_hash, refresh_expires_at, _ = create_refresh_token(user_id=user_uuid)

        await self.repo.revoke_refresh_token(token_hash)
        await self.repo.store_refresh_token(user_id=user_uuid, token_hash=new_hash, expires_at=refresh_expires_at)
        await self.session.commit()

        return user_uuid, AuthTokens(
            access_token=new_access,
            refresh_token=new_refresh,
            refresh_expires_at=refresh_expires_at,
        )

    async def logout(self, user_id: uuid.UUID | None, refresh_token: str | None) -> None:
        if refresh_token:
            await self.repo.revoke_refresh_token(hash_token(refresh_token))

        if user_id:
            await self.repo.revoke_all_user_tokens(user_id)

        await self.session.commit()

    async def get_user(self, user_id: uuid.UUID):
        user = await self.repo.get_user_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user
