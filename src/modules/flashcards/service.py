import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
from fastapi import HTTPException, status
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.infrastructure.database.session import AsyncSessionFactory
from src.models.flashcard import Flashcard
from src.models.flashcard_set import FlashcardSet
from src.models.user import User
from src.modules.flashcards.repository import FlashcardsRepository
from src.modules.flashcards.schemas import (
    FlashcardAlgorithm,
    FlashcardGenerateRequest,
    FlashcardItemResponse,
    ManualFlashcardCardCreateRequest,
    ManualFlashcardCardUpdateRequest,
    ManualFlashcardSetCreateRequest,
    ManualFlashcardSetResponse,
    ManualFlashcardSetUpdateRequest,
    FlashcardQueuedResponse,
    FlashcardReviewRating,
    FlashcardReviewRequest,
    FlashcardReviewResponse,
    FlashcardReviewTodayResponse,
    FlashcardSetDetailResponse,
    FlashcardSetListItemResponse,
    FlashcardType,
)


class _LLMFlashcardItem(BaseModel):
    card_type: FlashcardType
    front: str = Field(min_length=1)
    back: str = Field(min_length=1)
    image_keyword: str | None = None


class _LLMFlashcardPayload(BaseModel):
    cards: list[_LLMFlashcardItem] = Field(min_length=1)


class FlashcardsService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = FlashcardsRepository(session)

    async def queue_flashcard_generation(
        self,
        *,
        payload: FlashcardGenerateRequest,
        current_user: User,
    ) -> FlashcardQueuedResponse:
        document = await self.repo.get_user_document(document_id=payload.document_id, user_id=current_user.id)
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

        if document.extraction_status != "completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Document extraction/vectorization is not completed yet",
            )

        settings = get_settings()
        if not settings.gemini_api_key:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="GEMINI_API_KEY is not configured")

        self._validate_page_range(
            start_page=payload.start_page,
            end_page=payload.end_page,
            document_total_pages=document.total_pages,
        )

        title = payload.title or f"Flashcards - {document.title}"
        options = {
            "card_count": payload.card_count,
            "start_page": payload.start_page,
            "end_page": payload.end_page,
            "include_images": payload.include_images,
        }

        flashcard_set = await self.repo.create_flashcard_set(
            document_id=payload.document_id,
            user_id=current_user.id,
            title=title,
            algorithm=payload.algorithm.value,
            options=options,
            card_count=payload.card_count,
        )
        await self.session.commit()

        return FlashcardQueuedResponse(
            set_id=flashcard_set.id,
            document_id=flashcard_set.document_id,
            title=flashcard_set.title,
            generation_status=flashcard_set.generation_status,
            card_count_requested=payload.card_count,
            algorithm=FlashcardAlgorithm(flashcard_set.algorithm or FlashcardAlgorithm.CUSTOM_V1.value),
            created_at=flashcard_set.created_at,
        )

    async def create_manual_set(
        self,
        *,
        payload: ManualFlashcardSetCreateRequest,
        current_user: User,
    ) -> ManualFlashcardSetResponse:
        if payload.document_id is not None:
            document = await self.repo.get_user_document(document_id=payload.document_id, user_id=current_user.id)
            if document is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

        flashcard_set = await self.repo.create_manual_flashcard_set(
            document_id=payload.document_id,
            user_id=current_user.id,
            title=payload.title.strip(),
            description=payload.description.strip() if payload.description else None,
            category=payload.category.strip() if payload.category else None,
        )
        await self.session.commit()
        return self._to_manual_set_response(flashcard_set)

    async def update_manual_set(
        self,
        *,
        set_id: uuid.UUID,
        payload: ManualFlashcardSetUpdateRequest,
        current_user: User,
    ) -> ManualFlashcardSetResponse:
        flashcard_set = await self.repo.get_user_flashcard_set(set_id=set_id, user_id=current_user.id)
        if flashcard_set is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flashcard set not found")

        updated = await self.repo.update_set_content(
            set_id=set_id,
            title=payload.title.strip() if payload.title is not None else None,
            description=payload.description.strip() if payload.description is not None else None,
            category=payload.category.strip() if payload.category is not None else None,
        )
        if updated is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flashcard set not found")

        await self.session.commit()
        return self._to_manual_set_response(updated)

    async def delete_manual_set(
        self,
        *,
        set_id: uuid.UUID,
        current_user: User,
    ) -> None:
        flashcard_set = await self.repo.get_user_flashcard_set(set_id=set_id, user_id=current_user.id)
        if flashcard_set is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flashcard set not found")

        await self.repo.delete_set(set_id=set_id)
        await self.session.commit()

    async def list_flashcard_sets(
        self,
        *,
        current_user: User,
        limit: int,
        offset: int,
        document_id: uuid.UUID | None,
    ) -> list[FlashcardSetListItemResponse]:
        sets = await self.repo.list_user_flashcard_sets(
            user_id=current_user.id,
            limit=limit,
            offset=offset,
            document_id=document_id,
        )
        now_at = datetime.now(UTC)
        set_ids = [item.id for item in sets]
        stats_map = await self.repo.get_set_learning_stats(
            user_id=current_user.id,
            set_ids=set_ids,
            now_at=now_at,
        )

        return [self._to_set_list_item(item, stats_map.get(item.id)) for item in sets]

    async def get_flashcard_set_detail(self, *, set_id: uuid.UUID, current_user: User) -> FlashcardSetDetailResponse:
        flashcard_set = await self.repo.get_user_flashcard_set(set_id=set_id, user_id=current_user.id)
        if flashcard_set is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flashcard set not found")

        return self._to_set_detail(flashcard_set)

    async def list_set_cards(
        self,
        *,
        set_id: uuid.UUID,
        current_user: User,
        limit: int,
        offset: int,
    ) -> list[FlashcardItemResponse]:
        flashcard_set = await self.repo.get_user_flashcard_set(set_id=set_id, user_id=current_user.id)
        if flashcard_set is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flashcard set not found")

        cards = await self.repo.list_cards_by_set(set_id=set_id, limit=limit, offset=offset)
        return [self._to_card_item(card) for card in cards]

    async def list_due_cards_today(
        self,
        *,
        current_user: User,
        limit: int,
        offset: int,
        set_id: uuid.UUID | None,
    ) -> list[FlashcardReviewTodayResponse]:
        now_at = datetime.now(UTC)
        due_rows = await self.repo.list_due_cards(
            user_id=current_user.id,
            now_at=now_at,
            limit=limit,
            offset=offset,
            set_id=set_id,
        )
        return [self._to_due_today_response(card, flashcard_set) for card, flashcard_set in due_rows]

    async def create_manual_card(
        self,
        *,
        set_id: uuid.UUID,
        payload: ManualFlashcardCardCreateRequest,
        current_user: User,
    ) -> FlashcardItemResponse:
        flashcard_set = await self.repo.get_user_flashcard_set(set_id=set_id, user_id=current_user.id)
        if flashcard_set is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flashcard set not found")

        now_at = datetime.now(UTC)
        card = await self.repo.create_card(
            set_id=set_id,
            card_type=payload.card_type.value,
            front=payload.front.strip(),
            back=payload.back.strip(),
            image_url=payload.image_url,
            image_keyword=payload.image_keyword,
            ease_factor=Decimal("2.50"),
            interval_days=1,
            repetitions=0,
            next_review_at=now_at,
        )

        card_count = await self.repo.count_cards_in_set(set_id=set_id)
        await self.repo.update_set_card_count(set_id=set_id, card_count=card_count)
        await self.session.commit()

        return self._to_card_item(card)

    async def update_manual_card(
        self,
        *,
        card_id: uuid.UUID,
        payload: ManualFlashcardCardUpdateRequest,
        current_user: User,
    ) -> FlashcardItemResponse:
        card = await self.repo.get_user_card(card_id=card_id, user_id=current_user.id)
        if card is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flashcard not found")

        provided_fields = payload.model_fields_set

        updated = await self.repo.update_card_content(
            card_id=card_id,
            card_type=payload.card_type.value if payload.card_type is not None else None,
            front=payload.front.strip() if payload.front is not None else None,
            back=payload.back.strip() if payload.back is not None else None,
            image_url=payload.image_url,
            image_keyword=payload.image_keyword,
            update_image_url="image_url" in provided_fields,
            update_image_keyword="image_keyword" in provided_fields,
        )
        if updated is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flashcard not found")

        await self.session.commit()
        return self._to_card_item(updated)

    async def delete_manual_card(
        self,
        *,
        card_id: uuid.UUID,
        current_user: User,
    ) -> None:
        card = await self.repo.get_user_card(card_id=card_id, user_id=current_user.id)
        if card is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flashcard not found")

        set_id = card.set_id
        await self.repo.delete_card(card_id=card_id)
        card_count = await self.repo.count_cards_in_set(set_id=set_id)
        await self.repo.update_set_card_count(set_id=set_id, card_count=card_count)
        await self.session.commit()

    async def review_card(
        self,
        *,
        card_id: uuid.UUID,
        payload: FlashcardReviewRequest,
        current_user: User,
    ) -> FlashcardReviewResponse:
        card = await self.repo.get_user_card(card_id=card_id, user_id=current_user.id)
        if card is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flashcard not found")

        now_at = datetime.now(UTC)
        ease_factor, interval_days = self._calculate_next_schedule(card=card, rating=payload.rating)
        repetitions = card.repetitions + 1
        next_review_at = now_at + timedelta(days=interval_days)

        await self.repo.update_card_review(
            card_id=card.id,
            ease_factor=ease_factor,
            interval_days=interval_days,
            repetitions=repetitions,
            next_review_at=next_review_at,
            last_rating=payload.rating.value,
        )
        await self.session.commit()

        return FlashcardReviewResponse(
            card_id=card.id,
            rating=payload.rating,
            ease_factor=float(ease_factor),
            interval_days=interval_days,
            repetitions=repetitions,
            next_review_at=next_review_at,
        )

    @staticmethod
    async def run_flashcard_pipeline(set_id: uuid.UUID) -> None:
        async with AsyncSessionFactory() as session:
            service = FlashcardsService(session=session)
            await service._run_flashcard_pipeline(set_id)

    async def _run_flashcard_pipeline(self, set_id: uuid.UUID) -> None:
        flashcard_set = await self.repo.get_set_by_id(set_id)
        if flashcard_set is None:
            return

        await self.repo.update_set_status(set_id=set_id, status_value="processing", generation_error=None)
        await self.session.commit()

        try:
            cards = await self._generate_flashcards(flashcard_set)
            options = flashcard_set.options or {}
            if options.get("include_images", True):
                await self._enrich_cards_with_images(cards)

            await self.repo.replace_cards(set_id=set_id, cards=cards)
            await self.repo.update_set_status(
                set_id=set_id,
                status_value="completed",
                generation_error=None,
                card_count=len(cards),
            )
            await self.session.commit()
        except Exception as exc:  # noqa: BLE001
            await self.session.rollback()
            await self.repo.update_set_status(
                set_id=set_id,
                status_value="failed",
                generation_error=str(exc)[:1000],
            )
            await self.session.commit()

    async def _generate_flashcards(self, flashcard_set: FlashcardSet) -> list[dict]:
        settings = get_settings()
        chunks = await self._collect_chunks(flashcard_set)
        if not chunks:
            raise RuntimeError("No embedded chunks matched the flashcard request")

        context = self._build_context(chunks)
        options = flashcard_set.options or {}
        card_count = int(options.get("card_count", flashcard_set.card_count))

        llm = ChatGoogleGenerativeAI(
            model=settings.google_summary_model,
            api_key=settings.gemini_api_key,
            temperature=0.2,
            request_timeout=settings.summary_request_timeout_seconds,
            model_kwargs={"response_mime_type": "application/json"},
        )

        last_error: Exception | None = None
        for _ in range(3):
            try:
                raw_content = await self._invoke_flashcard_llm(llm=llm, card_count=card_count, context=context)
                payload = self._parse_flashcard_payload(raw_content=raw_content, expected_count=card_count)
                return self._normalize_cards(payload.cards)
            except (ValidationError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc

        raise RuntimeError(f"Failed to generate valid flashcards JSON after retries: {last_error}")

    async def _collect_chunks(self, flashcard_set: FlashcardSet):
        options = flashcard_set.options or {}
        start_page = options.get("start_page")
        end_page = options.get("end_page")

        if isinstance(start_page, int) and isinstance(end_page, int):
            return await self.repo.get_embedded_chunks_by_page_range(
                document_id=flashcard_set.document_id,
                start_page=start_page,
                end_page=end_page,
            )

        return await self.repo.get_all_embedded_chunks(flashcard_set.document_id)

    async def _invoke_flashcard_llm(
        self,
        *,
        llm: ChatGoogleGenerativeAI,
        card_count: int,
        context: str,
    ) -> str:
        response = await llm.ainvoke([
            ("system", self._flashcard_system_prompt()),
            ("human", self._flashcard_user_prompt(card_count=card_count, context=context)),
        ])

        content = getattr(response, "content", "")
        if content is None:
            raise ValueError("LLM returned empty content")

        if isinstance(content, str):
            text = content.strip()
            if not text:
                raise ValueError("LLM returned blank text content")
            return text
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and "text" in item:
                    parts.append(str(item["text"]))
            joined = "\n".join(parts).strip()
            if not joined:
                raise ValueError("LLM returned list content without text")
            return joined

        text = str(content).strip()
        if not text or text.lower() == "none":
            raise ValueError("LLM returned non-usable content")
        return text

    async def _enrich_cards_with_images(self, cards: list[dict]) -> None:
        settings = get_settings()
        if not settings.pixabay_api_key:
            return

        timeout = httpx.Timeout(settings.pixabay_request_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            for card in cards:
                keyword = str(card.get("image_keyword") or "").strip()
                if not keyword:
                    continue

                try:
                    response = await client.get(
                        settings.pixabay_base_url,
                        params={
                            "key": settings.pixabay_api_key,
                            "q": keyword,
                            "image_type": "photo",
                            "safesearch": "true",
                            "per_page": 3,
                            "order": "popular",
                        },
                    )
                    response.raise_for_status()
                    payload = response.json()
                    hits = payload.get("hits", [])
                    if hits:
                        first_hit = hits[0]
                        card["image_url"] = first_hit.get("webformatURL") or first_hit.get("largeImageURL")
                except Exception:  # noqa: BLE001
                    # Do not fail the whole deck when image enrichment fails.
                    continue

    def _parse_flashcard_payload(self, *, raw_content: str, expected_count: int) -> _LLMFlashcardPayload:
        cleaned = self._extract_json_object(self._strip_markdown_code_fences(raw_content).strip())
        payload_dict = json.loads(cleaned)
        payload = _LLMFlashcardPayload.model_validate(payload_dict)

        if len(payload.cards) != expected_count:
            raise ValueError(f"Expected {expected_count} cards, got {len(payload.cards)}")

        normalized_pairs = [f"{card.card_type.value}|{card.front.strip().lower()}" for card in payload.cards]
        if len(set(normalized_pairs)) != len(normalized_pairs):
            raise ValueError("Flashcards contain duplicate entries")

        return payload

    def _normalize_cards(self, cards: list[_LLMFlashcardItem]) -> list[dict]:
        now_at = datetime.now(UTC)
        normalized: list[dict] = []
        for card in cards:
            normalized.append(
                {
                    "card_type": card.card_type.value,
                    "front": card.front.strip(),
                    "back": card.back.strip(),
                    "image_url": None,
                    "image_keyword": (card.image_keyword or "").strip() or None,
                    "ease_factor": Decimal("2.50"),
                    "interval_days": 1,
                    "repetitions": 0,
                    "next_review_at": now_at,
                    "last_rating": None,
                }
            )

        return normalized

    def _calculate_next_schedule(
        self,
        *,
        card: Flashcard,
        rating: FlashcardReviewRating,
    ) -> tuple[Decimal, int]:
        current_ease = Decimal(card.ease_factor or Decimal("2.50"))
        current_interval = int(card.interval_days or 1)

        if rating == FlashcardReviewRating.HARD:
            next_ease = max(Decimal("1.30"), current_ease - Decimal("0.15"))
            next_interval = 1
        elif rating == FlashcardReviewRating.MEDIUM:
            next_ease = min(Decimal("2.80"), current_ease + Decimal("0.00"))
            next_interval = max(2, int(round(current_interval * 1.4)))
        else:
            next_ease = min(Decimal("2.80"), current_ease + Decimal("0.10"))
            next_interval = max(4, int(round(current_interval * 1.9)))

        return (next_ease.quantize(Decimal("0.01")), next_interval)

    def _to_set_list_item(
        self,
        flashcard_set: FlashcardSet,
        stats: dict[str, int] | None = None,
    ) -> FlashcardSetListItemResponse:
        total_cards = int(stats.get("total_cards", flashcard_set.card_count) if stats else flashcard_set.card_count)
        studied_cards = int(stats.get("studied_cards", 0) if stats else 0)
        due_cards = int(stats.get("due_cards", 0) if stats else 0)

        if total_cards == 0 or studied_cards == 0:
            learning_status = "chua_hoc"
        elif due_cards > 0:
            learning_status = "dang_hoc"
        else:
            learning_status = "da_hoc_xong"

        return FlashcardSetListItemResponse(
            set_id=flashcard_set.id,
            document_id=flashcard_set.document_id,
            title=flashcard_set.title,
            algorithm=flashcard_set.algorithm,
            generation_status=flashcard_set.generation_status,
            learning_status=learning_status,
            studied_cards=studied_cards,
            due_cards=due_cards,
            card_count=flashcard_set.card_count,
            completed_at=flashcard_set.completed_at,
            created_at=flashcard_set.created_at,
        )

    def _to_set_detail(self, flashcard_set: FlashcardSet) -> FlashcardSetDetailResponse:
        return FlashcardSetDetailResponse(
            set_id=flashcard_set.id,
            document_id=flashcard_set.document_id,
            title=flashcard_set.title,
            algorithm=flashcard_set.algorithm,
            generation_status=flashcard_set.generation_status,
            generation_error=flashcard_set.generation_error,
            card_count=flashcard_set.card_count,
            options=flashcard_set.options,
            completed_at=flashcard_set.completed_at,
            created_at=flashcard_set.created_at,
        )

    def _to_manual_set_response(self, flashcard_set: FlashcardSet) -> ManualFlashcardSetResponse:
        return ManualFlashcardSetResponse(
            set_id=flashcard_set.id,
            document_id=flashcard_set.document_id,
            title=flashcard_set.title,
            algorithm=flashcard_set.algorithm,
            generation_status=flashcard_set.generation_status,
            card_count=flashcard_set.card_count,
            options=flashcard_set.options,
            completed_at=flashcard_set.completed_at,
            created_at=flashcard_set.created_at,
        )

    def _to_card_item(self, card: Flashcard) -> FlashcardItemResponse:
        return FlashcardItemResponse(
            card_id=card.id,
            set_id=card.set_id,
            card_type=FlashcardType(card.card_type),
            front=card.front,
            back=card.back,
            image_url=card.image_url,
            image_keyword=card.image_keyword,
            ease_factor=float(card.ease_factor) if card.ease_factor is not None else None,
            interval_days=card.interval_days,
            repetitions=card.repetitions,
            next_review_at=card.next_review_at,
            last_rating=FlashcardReviewRating(card.last_rating) if card.last_rating else None,
        )

    def _to_due_today_response(self, card: Flashcard, flashcard_set: FlashcardSet) -> FlashcardReviewTodayResponse:
        if card.next_review_at is None:
            raise ValueError("Card next_review_at is missing for due list")

        return FlashcardReviewTodayResponse(
            card_id=card.id,
            set_id=card.set_id,
            set_title=flashcard_set.title,
            card_type=FlashcardType(card.card_type),
            front=card.front,
            back=card.back,
            image_url=card.image_url,
            image_keyword=card.image_keyword,
            ease_factor=float(card.ease_factor) if card.ease_factor is not None else None,
            interval_days=card.interval_days,
            repetitions=card.repetitions,
            next_review_at=card.next_review_at,
            last_rating=FlashcardReviewRating(card.last_rating) if card.last_rating else None,
        )

    def _build_context(self, chunks) -> str:
        return "\n\n".join(
            [
                f"[Page {chunk.page_number} | Chunk {chunk.chunk_index}]\n{chunk.text_content.strip()}"
                for chunk in chunks
                if chunk.text_content.strip()
            ]
        )

    def _validate_page_range(
        self,
        *,
        start_page: int | None,
        end_page: int | None,
        document_total_pages: int | None,
    ) -> None:
        if start_page is None and end_page is None:
            return

        if start_page is None or end_page is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="start_page and end_page must be provided together",
            )

        if start_page > end_page:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="start_page must be less than or equal to end_page",
            )

        if document_total_pages is not None and end_page > document_total_pages:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="end_page exceeds document total_pages",
            )

    def _flashcard_system_prompt(self) -> str:
        return (
            "You are an educational flashcard generator. "
            "Generate high-quality study cards from source context. "
            "Return ONLY strict JSON matching the requested schema."
        )

    def _flashcard_user_prompt(self, *, card_count: int, context: str) -> str:
        return (
            f"Generate exactly {card_count} flashcards from the context below.\n"
            "Requirements:\n"
            "- Mix three card types naturally based on content coverage: term_definition, qa, cloze.\n"
            "- card_type must be one of: term_definition, qa, cloze.\n"
            "- front and back must be concise and clear.\n"
            "- For cloze, front should contain a blank represented by '____'.\n"
            "- back should provide the missing answer and one-line explanation.\n"
            "- image_keyword should be 1-3 words in English for searching educational photos.\n"
            "- Avoid duplicates.\n"
            "Output JSON schema:\n"
            "{\n"
            '  "cards": [\n'
            "    {\n"
            '      "card_type": "term_definition|qa|cloze",\n'
            '      "front": "...",\n'
            '      "back": "...",\n'
            '      "image_keyword": "..."\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Context:\n"
            f"{context}"
        )

    def _strip_markdown_code_fences(self, value: str) -> str:
        text = value.strip()
        text = re.sub(r"^```json\\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^```\\s*", "", text)
        text = re.sub(r"\\s*```$", "", text)
        return text

    def _extract_json_object(self, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("LLM response is empty")

        start_idx = text.find("{")
        end_idx = text.rfind("}")
        if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
            raise ValueError("LLM response does not contain a valid JSON object")

        return text[start_idx : end_idx + 1]
