import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.refresh_token import RefreshToken
from src.models.user import User
from src.modules.auth.schemas import GoogleProfile


class AuthRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        query = select(User).where(User.id == user_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_user_by_google_id(self, google_id: str) -> User | None:
        query = select(User).where(User.google_id == google_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create_or_update_google_user(self, profile: GoogleProfile) -> User:
        user = await self.get_user_by_google_id(profile.google_id)
        if user is None:
            user = User(
                google_id=profile.google_id,
                email=str(profile.email),
                full_name=profile.full_name,
                avatar_url=str(profile.avatar_url) if profile.avatar_url else None,
            )
            self.session.add(user)
            await self.session.flush()
            return user

        user.email = str(profile.email)
        user.full_name = profile.full_name
        user.avatar_url = str(profile.avatar_url) if profile.avatar_url else None
        await self.session.flush()
        return user

    async def store_refresh_token(self, *, user_id: uuid.UUID, token_hash: str, expires_at: datetime) -> None:
        record = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self.session.add(record)
        await self.session.flush()

    async def find_valid_refresh_token(self, token_hash: str) -> RefreshToken | None:
        now = datetime.now(UTC)
        query = select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def revoke_refresh_token(self, token_hash: str) -> None:
        now = datetime.now(UTC)
        query = (
            update(RefreshToken)
            .where(RefreshToken.token_hash == token_hash, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await self.session.execute(query)

    async def revoke_all_user_tokens(self, user_id: uuid.UUID) -> None:
        now = datetime.now(UTC)
        query = (
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await self.session.execute(query)
