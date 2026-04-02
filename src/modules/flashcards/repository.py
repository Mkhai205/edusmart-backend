import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import and_, case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import Document
from src.models.document_chunk import DocumentChunk
from src.models.flashcard import Flashcard
from src.models.flashcard_set import FlashcardSet


class FlashcardsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_document(self, document_id: uuid.UUID, user_id: uuid.UUID) -> Document | None:
        query = select(Document).where(Document.id == document_id, Document.user_id == user_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create_manual_flashcard_set(
        self,
        *,
        document_id: uuid.UUID | None,
        user_id: uuid.UUID,
        title: str,
        description: str | None,
        category: str | None,
    ) -> FlashcardSet:
        options = {
            "manual": True,
            "description": description,
            "category": category,
        }
        flashcard_set = FlashcardSet(
            document_id=document_id,
            user_id=user_id,
            title=title,
            algorithm="manual_v1",
            card_count=0,
            options=options,
            generation_status="completed",
            generation_error=None,
            completed_at=datetime.now(UTC),
        )
        self.session.add(flashcard_set)
        await self.session.flush()
        return flashcard_set

    async def create_flashcard_set(
        self,
        *,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str,
        algorithm: str,
        options: dict,
        card_count: int,
    ) -> FlashcardSet:
        flashcard_set = FlashcardSet(
            document_id=document_id,
            user_id=user_id,
            title=title,
            algorithm=algorithm,
            card_count=card_count,
            options=options,
            generation_status="pending",
            generation_error=None,
            completed_at=None,
        )
        self.session.add(flashcard_set)
        await self.session.flush()
        return flashcard_set

    async def get_set_by_id(self, set_id: uuid.UUID) -> FlashcardSet | None:
        query = select(FlashcardSet).where(FlashcardSet.id == set_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_user_flashcard_set(self, set_id: uuid.UUID, user_id: uuid.UUID) -> FlashcardSet | None:
        query = select(FlashcardSet).where(FlashcardSet.id == set_id, FlashcardSet.user_id == user_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_user_flashcard_sets(
        self,
        *,
        user_id: uuid.UUID,
        limit: int,
        offset: int,
        document_id: uuid.UUID | None = None,
    ) -> list[FlashcardSet]:
        query = select(FlashcardSet).where(FlashcardSet.user_id == user_id)
        if document_id is not None:
            query = query.where(FlashcardSet.document_id == document_id)

        query = query.order_by(FlashcardSet.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_set_learning_stats(
        self,
        *,
        user_id: uuid.UUID,
        set_ids: list[uuid.UUID],
        now_at: datetime,
    ) -> dict[uuid.UUID, dict[str, int]]:
        if not set_ids:
            return {}

        studied_expr = case((Flashcard.repetitions > 0, 1), else_=0)
        due_expr = case(
            (
                and_(
                    Flashcard.next_review_at.is_not(None),
                    Flashcard.next_review_at <= now_at,
                ),
                1,
            ),
            else_=0,
        )

        query = (
            select(
                Flashcard.set_id,
                func.count(Flashcard.id).label("total_cards"),
                func.sum(studied_expr).label("studied_cards"),
                func.sum(due_expr).label("due_cards"),
            )
            .join(FlashcardSet, Flashcard.set_id == FlashcardSet.id)
            .where(
                FlashcardSet.user_id == user_id,
                Flashcard.set_id.in_(set_ids),
            )
            .group_by(Flashcard.set_id)
        )

        result = await self.session.execute(query)
        rows = result.all()

        stats: dict[uuid.UUID, dict[str, int]] = {}
        for set_id, total_cards, studied_cards, due_cards in rows:
            stats[set_id] = {
                "total_cards": int(total_cards or 0),
                "studied_cards": int(studied_cards or 0),
                "due_cards": int(due_cards or 0),
            }

        return stats

    async def update_set_status(
        self,
        *,
        set_id: uuid.UUID,
        status_value: str,
        generation_error: str | None = None,
        card_count: int | None = None,
    ) -> None:
        flashcard_set = await self.get_set_by_id(set_id)
        if flashcard_set is None:
            return

        flashcard_set.generation_status = status_value
        flashcard_set.generation_error = generation_error
        if card_count is not None:
            flashcard_set.card_count = card_count

        if status_value == "completed":
            flashcard_set.completed_at = datetime.now(UTC)
        elif status_value in {"pending", "processing"}:
            flashcard_set.completed_at = None

        await self.session.flush()

    async def replace_cards(self, *, set_id: uuid.UUID, cards: list[dict]) -> None:
        await self.session.execute(delete(Flashcard).where(Flashcard.set_id == set_id))

        records = [
            Flashcard(
                set_id=set_id,
                card_type=card["card_type"],
                front=card["front"],
                back=card["back"],
                image_url=card.get("image_url"),
                image_keyword=card.get("image_keyword"),
                ease_factor=card.get("ease_factor"),
                interval_days=card.get("interval_days"),
                repetitions=card.get("repetitions", 0),
                next_review_at=card.get("next_review_at"),
                last_rating=card.get("last_rating"),
            )
            for card in cards
        ]
        self.session.add_all(records)
        await self.session.flush()

    async def list_cards_by_set(self, *, set_id: uuid.UUID, limit: int, offset: int) -> list[Flashcard]:
        query = (
            select(Flashcard)
            .where(Flashcard.set_id == set_id)
            .order_by(Flashcard.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create_card(
        self,
        *,
        set_id: uuid.UUID,
        card_type: str,
        front: str,
        back: str,
        image_url: str | None,
        image_keyword: str | None,
        ease_factor: Decimal,
        interval_days: int,
        repetitions: int,
        next_review_at: datetime,
    ) -> Flashcard:
        card = Flashcard(
            set_id=set_id,
            card_type=card_type,
            front=front,
            back=back,
            image_url=image_url,
            image_keyword=image_keyword,
            ease_factor=ease_factor,
            interval_days=interval_days,
            repetitions=repetitions,
            next_review_at=next_review_at,
            last_rating=None,
        )
        self.session.add(card)
        await self.session.flush()
        return card

    async def update_card_content(
        self,
        *,
        card_id: uuid.UUID,
        card_type: str | None,
        front: str | None,
        back: str | None,
        image_url: str | None,
        image_keyword: str | None,
        update_image_url: bool,
        update_image_keyword: bool,
    ) -> Flashcard | None:
        card = await self.get_card_by_id(card_id)
        if card is None:
            return None

        if card_type is not None:
            card.card_type = card_type
        if front is not None:
            card.front = front
        if back is not None:
            card.back = back

        if update_image_url:
            card.image_url = image_url
        if update_image_keyword:
            card.image_keyword = image_keyword
        await self.session.flush()
        return card

    async def delete_card(self, *, card_id: uuid.UUID) -> None:
        await self.session.execute(delete(Flashcard).where(Flashcard.id == card_id))
        await self.session.flush()

    async def count_cards_in_set(self, *, set_id: uuid.UUID) -> int:
        query = select(Flashcard).where(Flashcard.set_id == set_id)
        result = await self.session.execute(query)
        return len(list(result.scalars().all()))

    async def update_set_card_count(self, *, set_id: uuid.UUID, card_count: int) -> None:
        flashcard_set = await self.get_set_by_id(set_id)
        if flashcard_set is None:
            return

        flashcard_set.card_count = card_count
        await self.session.flush()

    async def update_set_content(
        self,
        *,
        set_id: uuid.UUID,
        title: str | None,
        description: str | None,
        category: str | None,
    ) -> FlashcardSet | None:
        flashcard_set = await self.get_set_by_id(set_id)
        if flashcard_set is None:
            return None

        if title is not None:
            flashcard_set.title = title

        options = dict(flashcard_set.options or {})
        if description is not None:
            options["description"] = description
        if category is not None:
            options["category"] = category
        flashcard_set.options = options
        await self.session.flush()
        return flashcard_set

    async def delete_set(self, *, set_id: uuid.UUID) -> None:
        await self.session.execute(delete(FlashcardSet).where(FlashcardSet.id == set_id))
        await self.session.flush()

    async def get_user_card(self, card_id: uuid.UUID, user_id: uuid.UUID) -> Flashcard | None:
        query = (
            select(Flashcard)
            .join(FlashcardSet, Flashcard.set_id == FlashcardSet.id)
            .where(Flashcard.id == card_id, FlashcardSet.user_id == user_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_due_cards(
        self,
        *,
        user_id: uuid.UUID,
        now_at: datetime,
        limit: int,
        offset: int,
        set_id: uuid.UUID | None = None,
    ) -> list[tuple[Flashcard, FlashcardSet]]:
        query = (
            select(Flashcard, FlashcardSet)
            .join(FlashcardSet, Flashcard.set_id == FlashcardSet.id)
            .where(
                FlashcardSet.user_id == user_id,
                FlashcardSet.generation_status == "completed",
                Flashcard.next_review_at.is_not(None),
                Flashcard.next_review_at <= now_at,
            )
            .order_by(Flashcard.next_review_at.asc(), Flashcard.created_at.asc())
            .limit(limit)
            .offset(offset)
        )

        if set_id is not None:
            query = query.where(FlashcardSet.id == set_id)

        result = await self.session.execute(query)
        return list(result.all())

    async def update_card_review(
        self,
        *,
        card_id: uuid.UUID,
        ease_factor: Decimal,
        interval_days: int,
        repetitions: int,
        next_review_at: datetime,
        last_rating: str,
    ) -> None:
        card = await self.get_card_by_id(card_id)
        if card is None:
            return

        card.ease_factor = ease_factor
        card.interval_days = interval_days
        card.repetitions = repetitions
        card.next_review_at = next_review_at
        card.last_rating = last_rating
        await self.session.flush()

    async def get_card_by_id(self, card_id: uuid.UUID) -> Flashcard | None:
        query = select(Flashcard).where(Flashcard.id == card_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_all_embedded_chunks(self, document_id: uuid.UUID) -> list[DocumentChunk]:
        query = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id, DocumentChunk.embedding.is_not(None))
            .order_by(DocumentChunk.page_number.asc(), DocumentChunk.chunk_index.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_embedded_chunks_by_page_range(
        self,
        *,
        document_id: uuid.UUID,
        start_page: int,
        end_page: int,
    ) -> list[DocumentChunk]:
        query = (
            select(DocumentChunk)
            .where(
                and_(
                    DocumentChunk.document_id == document_id,
                    DocumentChunk.embedding.is_not(None),
                    DocumentChunk.page_number >= start_page,
                    DocumentChunk.page_number <= end_page,
                )
            )
            .order_by(DocumentChunk.page_number.asc(), DocumentChunk.chunk_index.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
