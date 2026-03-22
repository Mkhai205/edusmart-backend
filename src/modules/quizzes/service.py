import json
import re
import uuid
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.infrastructure.database.session import AsyncSessionFactory
from src.models.document_chunk import DocumentChunk
from src.models.quiz import Quiz
from src.models.user import User
from src.modules.quizzes.repository import QuizzesRepository
from src.modules.quizzes.schemas import (
    QuizAttemptListItemResponse,
    QuizDetailResponse,
    QuizDifficulty,
    QuizGenerateRequest,
    QuizListItemResponse,
    QuizQuestion,
    QuizQuestionResult,
    QuizQueuedResponse,
    QuizSubmitRequest,
    QuizSubmitResponse,
    QuizType,
)


class _LLMQuizQuestion(BaseModel):
    question_text: str = Field(min_length=1)
    options: list[str] = Field(min_length=4, max_length=4)
    correct_option_index: int = Field(ge=0, le=3)
    hint: str = Field(min_length=1)
    option_explanations: list[str] = Field(min_length=4, max_length=4)


class _LLMQuizPayload(BaseModel):
    questions: list[_LLMQuizQuestion] = Field(min_length=1)


class QuizzesService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = QuizzesRepository(session)

    async def queue_quiz_generation(self, *, payload: QuizGenerateRequest, current_user: User) -> QuizQueuedResponse:
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

        options = {
            "question_count": payload.question_count,
            "difficulty": payload.difficulty.value,
            "start_page": payload.start_page,
            "end_page": payload.end_page,
        }
        quiz = await self.repo.create_quiz(
            document_id=payload.document_id,
            user_id=current_user.id,
            title=f"Quiz - {document.title}",
            quiz_type=QuizType.MULTIPLE_CHOICE_SINGLE.value,
            difficulty=payload.difficulty.value,
            time_limit=payload.time_limit_seconds,
            options=options,
        )
        await self.session.commit()

        return QuizQueuedResponse(
            quiz_id=quiz.id,
            document_id=quiz.document_id,
            quiz_status=quiz.quiz_status,
            quiz_type=QuizType(quiz.quiz_type),
            question_count=payload.question_count,
            difficulty=payload.difficulty,
            start_page=payload.start_page,
            end_page=payload.end_page,
            time_limit_seconds=quiz.time_limit,
            created_at=quiz.created_at,
        )

    async def get_quiz_detail(self, *, quiz_id: uuid.UUID, current_user: User) -> QuizDetailResponse:
        quiz = await self.repo.get_user_quiz(quiz_id=quiz_id, user_id=current_user.id)
        if quiz is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")

        return self._to_detail_response(quiz)

    async def list_quizzes(
        self,
        *,
        current_user: User,
        limit: int,
        offset: int,
        document_id: uuid.UUID | None,
    ) -> list[QuizListItemResponse]:
        quizzes = await self.repo.list_user_quizzes(
            user_id=current_user.id,
            limit=limit,
            offset=offset,
            document_id=document_id,
        )
        return [self._to_list_item_response(quiz) for quiz in quizzes]

    async def submit_quiz(
        self,
        *,
        quiz_id: uuid.UUID,
        payload: QuizSubmitRequest,
        current_user: User,
    ) -> QuizSubmitResponse:
        quiz = await self.repo.get_user_quiz(quiz_id=quiz_id, user_id=current_user.id)
        if quiz is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")

        if quiz.quiz_status != "completed" or not quiz.questions:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Quiz is not ready for submission")

        questions = [QuizQuestion.model_validate(item) for item in quiz.questions]
        question_count = len(questions)
        answer_map = {answer.question_index: answer.selected_option_index for answer in payload.answers}

        invalid_indexes = [
            question_index
            for question_index in answer_map
            if question_index < 1 or question_index > question_count
        ]
        if invalid_indexes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid question_index values: {invalid_indexes}",
            )

        results: list[QuizQuestionResult] = []
        correct_count = 0
        incorrect_count = 0
        skipped_count = 0

        for question in questions:
            selected_option_index = answer_map.get(question.question_index)
            is_skipped = selected_option_index is None
            is_correct = False
            explanation = question.correct_explanation

            if is_skipped:
                skipped_count += 1
                explanation = f"Skipped question. Hint: {question.hint}"
            elif selected_option_index == question.correct_option_index:
                correct_count += 1
                is_correct = True
                explanation = question.correct_explanation
            else:
                incorrect_count += 1
                explanation = question.option_explanations[selected_option_index]

            results.append(
                QuizQuestionResult(
                    question_index=question.question_index,
                    selected_option_index=selected_option_index,
                    correct_option_index=question.correct_option_index,
                    is_correct=is_correct,
                    is_skipped=is_skipped,
                    explanation=explanation,
                )
            )

        score = Decimal(0)
        if question_count > 0:
            score = (Decimal(correct_count) * Decimal("100.00") / Decimal(question_count)).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )

        serialized_answers = [answer.model_dump() for answer in payload.answers]
        attempt = await self.repo.create_quiz_attempt(
            quiz_id=quiz.id,
            user_id=current_user.id,
            answers=serialized_answers,
            score=score,
            total_questions=question_count,
            time_spent=payload.time_spent_seconds,
        )
        await self.session.commit()

        return QuizSubmitResponse(
            attempt_id=attempt.id,
            quiz_id=quiz.id,
            score=float(attempt.score),
            total_questions=question_count,
            correct_count=correct_count,
            incorrect_count=incorrect_count,
            skipped_count=skipped_count,
            time_spent_seconds=attempt.time_spent,
            completed_at=attempt.completed_at,
            results=results,
        )

    async def list_quiz_attempts(
        self,
        *,
        quiz_id: uuid.UUID,
        current_user: User,
        limit: int,
        offset: int,
    ) -> list[QuizAttemptListItemResponse]:
        quiz = await self.repo.get_user_quiz(quiz_id=quiz_id, user_id=current_user.id)
        if quiz is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")

        attempts = await self.repo.list_quiz_attempts(
            quiz_id=quiz_id,
            user_id=current_user.id,
            limit=limit,
            offset=offset,
        )
        return [
            QuizAttemptListItemResponse(
                attempt_id=attempt.id,
                quiz_id=attempt.quiz_id,
                score=float(attempt.score),
                total_questions=attempt.total_questions,
                time_spent_seconds=attempt.time_spent,
                completed_at=attempt.completed_at,
            )
            for attempt in attempts
        ]

    @staticmethod
    async def run_quiz_pipeline(quiz_id: uuid.UUID) -> None:
        async with AsyncSessionFactory() as session:
            service = QuizzesService(session=session)
            await service._run_quiz_pipeline(quiz_id)

    async def _run_quiz_pipeline(self, quiz_id: uuid.UUID) -> None:
        quiz = await self.repo.get_quiz_by_id(quiz_id)
        if quiz is None:
            return

        await self.repo.update_quiz_status(quiz_id=quiz_id, status_value="processing", quiz_error=None)
        await self.session.commit()

        try:
            questions = await self._generate_quiz_questions(quiz=quiz)
            await self.repo.update_quiz_questions(quiz_id=quiz_id, questions=questions)
            await self.repo.update_quiz_status(quiz_id=quiz_id, status_value="completed", quiz_error=None)
            await self.session.commit()
        except Exception as exc:  # noqa: BLE001
            await self.session.rollback()
            await self.repo.update_quiz_status(
                quiz_id=quiz_id,
                status_value="failed",
                quiz_error=str(exc)[:1000],
            )
            await self.session.commit()

    async def _generate_quiz_questions(self, *, quiz: Quiz) -> list[dict]:
        settings = get_settings()
        chunks = await self._collect_chunks(quiz)
        if not chunks:
            raise RuntimeError("No embedded chunks matched the quiz request")

        context = self._build_context(chunks)
        options = quiz.options or {}
        question_count = int(options.get("question_count", 10))
        difficulty = str(options.get("difficulty", QuizDifficulty.MEDIUM.value))

        llm = ChatGoogleGenerativeAI(
            model=settings.google_summary_model,
            api_key=settings.gemini_api_key,
            temperature=0.2,
            request_timeout=settings.summary_request_timeout_seconds,
        )

        last_error: Exception | None = None
        for _ in range(3):
            try:
                raw_content = await self._invoke_quiz_llm(
                    llm=llm,
                    question_count=question_count,
                    difficulty=difficulty,
                    context=context,
                )
                payload = self._parse_quiz_payload(raw_content=raw_content, expected_count=question_count)
                return self._normalize_questions(payload.questions)
            except (ValidationError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc

        raise RuntimeError(f"Failed to generate valid quiz JSON after retries: {last_error}")

    async def _collect_chunks(self, quiz: Quiz) -> list[DocumentChunk]:
        options = quiz.options or {}
        start_page = options.get("start_page")
        end_page = options.get("end_page")

        if isinstance(start_page, int) and isinstance(end_page, int):
            return await self.repo.get_embedded_chunks_by_page_range(
                document_id=quiz.document_id,
                start_page=start_page,
                end_page=end_page,
            )

        return await self.repo.get_all_embedded_chunks(quiz.document_id)

    async def _invoke_quiz_llm(
        self,
        *,
        llm: ChatGoogleGenerativeAI,
        question_count: int,
        difficulty: str,
        context: str,
    ) -> str:
        response = await llm.ainvoke([
            ("system", self._quiz_system_prompt()),
            (
                "human",
                self._quiz_user_prompt(
                    question_count=question_count,
                    difficulty=difficulty,
                    context=context,
                ),
            ),
        ])

        content = getattr(response, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and "text" in item:
                    parts.append(str(item["text"]))
            return "\n".join(parts)
        return str(content)

    def _parse_quiz_payload(self, *, raw_content: str, expected_count: int) -> _LLMQuizPayload:
        cleaned = self._strip_markdown_code_fences(raw_content).strip()
        payload_dict = json.loads(cleaned)
        payload = _LLMQuizPayload.model_validate(payload_dict)

        if len(payload.questions) != expected_count:
            raise ValueError(f"Expected {expected_count} questions, got {len(payload.questions)}")

        normalized_texts = [question.question_text.strip().lower() for question in payload.questions]
        if len(set(normalized_texts)) != len(normalized_texts):
            raise ValueError("Quiz contains duplicate questions")

        return payload

    def _normalize_questions(self, questions: list[_LLMQuizQuestion]) -> list[dict]:
        normalized: list[dict] = []
        for index, question in enumerate(questions, start=1):
            option_explanations = [explanation.strip() for explanation in question.option_explanations]
            incorrect_explanations = [
                explanation
                for idx, explanation in enumerate(option_explanations)
                if idx != question.correct_option_index
            ]
            quiz_question = QuizQuestion(
                question_index=index,
                question_text=question.question_text.strip(),
                options=[option.strip() for option in question.options],
                correct_option_index=question.correct_option_index,
                hint=question.hint.strip(),
                correct_explanation=option_explanations[question.correct_option_index],
                incorrect_explanations=incorrect_explanations,
                option_explanations=option_explanations,
            )
            normalized.append(quiz_question.model_dump())

        return normalized

    def _to_detail_response(self, quiz: Quiz) -> QuizDetailResponse:
        options = quiz.options or {}
        questions: list[QuizQuestion] | None = None
        if quiz.quiz_status == "completed" and quiz.questions:
            questions = [QuizQuestion.model_validate(item) for item in quiz.questions]

        return QuizDetailResponse(
            quiz_id=quiz.id,
            document_id=quiz.document_id,
            title=quiz.title,
            quiz_type=QuizType(quiz.quiz_type),
            quiz_status=quiz.quiz_status,
            question_count=int(options.get("question_count", 0)),
            difficulty=QuizDifficulty(str(options.get("difficulty", QuizDifficulty.MEDIUM.value))),
            start_page=options.get("start_page"),
            end_page=options.get("end_page"),
            time_limit_seconds=quiz.time_limit,
            questions=questions,
            quiz_error=quiz.quiz_error,
            completed_at=quiz.completed_at,
            created_at=quiz.created_at,
        )

    def _to_list_item_response(self, quiz: Quiz) -> QuizListItemResponse:
        options = quiz.options or {}
        return QuizListItemResponse(
            quiz_id=quiz.id,
            document_id=quiz.document_id,
            title=quiz.title,
            quiz_type=QuizType(quiz.quiz_type),
            quiz_status=quiz.quiz_status,
            question_count=int(options.get("question_count", 0)),
            difficulty=QuizDifficulty(str(options.get("difficulty", QuizDifficulty.MEDIUM.value))),
            time_limit_seconds=quiz.time_limit,
            completed_at=quiz.completed_at,
            created_at=quiz.created_at,
        )

    def _validate_page_range(self, *, start_page: int | None, end_page: int | None, document_total_pages: int | None) -> None:
        if start_page is None or end_page is None:
            return

        if document_total_pages is not None and end_page > document_total_pages:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"end_page exceeds total pages ({document_total_pages})",
            )

    def _build_context(self, chunks: list[DocumentChunk]) -> str:
        max_chunks = 80
        selected = chunks[:max_chunks]
        blocks = [f"[page={chunk.page_number}, chunk={chunk.chunk_index}] {chunk.text_content}" for chunk in selected]
        return "\n\n".join(blocks)

    def _quiz_system_prompt(self) -> str:
        return (
            "Bạn là trợ lý tạo câu hỏi trắc nghiệm học thuật. "
            "Nhiệm vụ: tạo câu hỏi 1 đáp án đúng từ tài liệu người dùng cung cấp. "
            "BẮT BUỘC trả về JSON hợp lệ, không được có markdown, không code fence, không giải thích ngoài JSON."
        )

    def _quiz_user_prompt(self, *, question_count: int, difficulty: str, context: str) -> str:
        return (
            "Tạo chính xác "
            f"{question_count} câu trắc nghiệm mức độ {difficulty}.\n"
            "Yêu cầu mỗi câu:\n"
            "- question_text: nội dung câu hỏi rõ ràng, không mơ hồ.\n"
            "- options: đúng 4 đáp án, không trùng nhau.\n"
            "- correct_option_index: chỉ số đáp án đúng (0-3).\n"
            "- hint: gợi ý ngắn, không lộ đáp án trực tiếp.\n"
            "- option_explanations: mảng 4 phần tử, giải thích cho từng đáp án theo đúng thứ tự options.\n"
            "- Không tạo câu hỏi trùng lặp.\n"
            "Định dạng JSON bắt buộc:\n"
            '{"questions": [{"question_text": "...", "options": ["...", "...", "...", "..."], "correct_option_index": 0, '
            '"hint": "...", "option_explanations": ["...", "...", "...", "..."]}]}\n'
            "Context tài liệu:\n"
            f"{context}"
        )

    def _strip_markdown_code_fences(self, text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?", "", stripped).strip()
            stripped = re.sub(r"```$", "", stripped).strip()
        return stripped
