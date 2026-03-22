import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import Document
from src.models.document_chunk import DocumentChunk
from src.models.quiz import Quiz
from src.models.quiz_attempt import QuizAttempt


class QuizzesRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_document(self, document_id: uuid.UUID, user_id: uuid.UUID) -> Document | None:
        query = select(Document).where(Document.id == document_id, Document.user_id == user_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create_quiz(
        self,
        *,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str,
        quiz_type: str,
        difficulty: str,
        time_limit: int,
        options: dict,
    ) -> Quiz:
        quiz = Quiz(
            document_id=document_id,
            user_id=user_id,
            title=title,
            questions=None,
            quiz_type=quiz_type,
            difficulty=difficulty,
            time_limit=time_limit,
            options=options,
            quiz_status="pending",
            quiz_error=None,
            completed_at=None,
        )
        self.session.add(quiz)
        await self.session.flush()
        return quiz

    async def get_user_quiz(self, quiz_id: uuid.UUID, user_id: uuid.UUID) -> Quiz | None:
        query = select(Quiz).where(Quiz.id == quiz_id, Quiz.user_id == user_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_user_quizzes(
        self,
        *,
        user_id: uuid.UUID,
        limit: int,
        offset: int,
        document_id: uuid.UUID | None = None,
    ) -> list[Quiz]:
        query = select(Quiz).where(Quiz.user_id == user_id)
        if document_id is not None:
            query = query.where(Quiz.document_id == document_id)

        query = query.order_by(Quiz.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_quiz_by_id(self, quiz_id: uuid.UUID) -> Quiz | None:
        query = select(Quiz).where(Quiz.id == quiz_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_quiz_status(
        self,
        *,
        quiz_id: uuid.UUID,
        status_value: str,
        quiz_error: str | None = None,
    ) -> None:
        quiz = await self.get_quiz_by_id(quiz_id)
        if quiz is None:
            return

        quiz.quiz_status = status_value
        quiz.quiz_error = quiz_error
        if status_value == "completed":
            quiz.completed_at = datetime.now(UTC)
        elif status_value in {"pending", "processing"}:
            quiz.completed_at = None

        await self.session.flush()

    async def update_quiz_questions(self, *, quiz_id: uuid.UUID, questions: list[dict]) -> None:
        quiz = await self.get_quiz_by_id(quiz_id)
        if quiz is None:
            return

        quiz.questions = questions
        await self.session.flush()

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
                DocumentChunk.document_id == document_id,
                DocumentChunk.embedding.is_not(None),
                DocumentChunk.page_number >= start_page,
                DocumentChunk.page_number <= end_page,
            )
            .order_by(DocumentChunk.page_number.asc(), DocumentChunk.chunk_index.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create_quiz_attempt(
        self,
        *,
        quiz_id: uuid.UUID,
        user_id: uuid.UUID,
        answers: list[dict],
        score: Decimal,
        total_questions: int,
        time_spent: int,
    ) -> QuizAttempt:
        attempt = QuizAttempt(
            quiz_id=quiz_id,
            user_id=user_id,
            answers=answers,
            score=score,
            total_questions=total_questions,
            time_spent=time_spent,
        )
        self.session.add(attempt)
        await self.session.flush()
        return attempt

    async def list_quiz_attempts(
        self,
        *,
        quiz_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> list[QuizAttempt]:
        query = (
            select(QuizAttempt)
            .where(QuizAttempt.quiz_id == quiz_id, QuizAttempt.user_id == user_id)
            .order_by(QuizAttempt.completed_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
