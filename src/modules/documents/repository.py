import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import Document


class DocumentsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_document(
        self,
        *,
        user_id: uuid.UUID,
        title: str,
        file_url: str,
        object_key: str,
        content_type: str,
        file_size: int,
        total_pages: int | None,
        is_public: bool,
    ) -> Document:
        document = Document(
            user_id=user_id,
            title=title,
            file_url=file_url,
            object_key=object_key,
            content_type=content_type,
            file_size=file_size,
            total_pages=total_pages,
            is_public=is_public,
        )
        self.session.add(document)
        await self.session.flush()
        return document

    async def get_user_document(self, document_id: uuid.UUID, user_id: uuid.UUID) -> Document | None:
        query = select(Document).where(Document.id == document_id, Document.user_id == user_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
