import uuid
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class QuizDifficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuizType(str, Enum):
    MULTIPLE_CHOICE_SINGLE = "multiple_choice_single"


QuizStatus = Literal["pending", "processing", "completed", "failed"]


class QuizGenerateRequest(BaseModel):
    document_id: uuid.UUID
    question_count: int = Field(default=10, ge=5, le=30)
    difficulty: QuizDifficulty = QuizDifficulty.MEDIUM
    start_page: int | None = Field(default=None, ge=1)
    end_page: int | None = Field(default=None, ge=1)
    time_limit_seconds: int = Field(default=900, ge=60, le=7200)

    @model_validator(mode="after")
    def validate_page_range(self) -> "QuizGenerateRequest":
        if (self.start_page is None) != (self.end_page is None):
            raise ValueError("start_page and end_page must be provided together")
        if self.start_page is not None and self.end_page is not None and self.start_page > self.end_page:
            raise ValueError("start_page must be less than or equal to end_page")
        return self


class QuizQuestion(BaseModel):
    question_index: int = Field(ge=1)
    question_text: str = Field(min_length=1)
    options: list[str] = Field(min_length=4, max_length=4)
    correct_option_index: int = Field(ge=0, le=3)
    hint: str = Field(min_length=1)
    correct_explanation: str = Field(min_length=1)
    incorrect_explanations: list[str] = Field(min_length=3, max_length=3)
    option_explanations: list[str] = Field(min_length=4, max_length=4)

    @model_validator(mode="after")
    def validate_options(self) -> "QuizQuestion":
        cleaned = [option.strip() for option in self.options]
        if len(set(cleaned)) != 4:
            raise ValueError("Each question must have 4 unique answer options")
        return self


class QuizQueuedResponse(BaseModel):
    quiz_id: uuid.UUID
    document_id: uuid.UUID
    quiz_status: QuizStatus
    quiz_type: QuizType
    question_count: int
    difficulty: QuizDifficulty
    start_page: int | None
    end_page: int | None
    time_limit_seconds: int
    created_at: datetime


class QuizDetailResponse(BaseModel):
    quiz_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    quiz_type: QuizType
    quiz_status: QuizStatus
    question_count: int
    difficulty: QuizDifficulty
    start_page: int | None
    end_page: int | None
    time_limit_seconds: int
    questions: list[QuizQuestion] | None
    quiz_error: str | None
    completed_at: datetime | None
    created_at: datetime


class QuizListItemResponse(BaseModel):
    quiz_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    quiz_type: QuizType
    quiz_status: QuizStatus
    question_count: int
    difficulty: QuizDifficulty
    time_limit_seconds: int
    completed_at: datetime | None
    created_at: datetime


class QuizSubmitAnswer(BaseModel):
    question_index: int = Field(ge=1)
    selected_option_index: int | None = Field(default=None, ge=0, le=3)


class QuizSubmitRequest(BaseModel):
    answers: list[QuizSubmitAnswer] = Field(default_factory=list)
    time_spent_seconds: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_unique_question_indexes(self) -> "QuizSubmitRequest":
        indexes = [answer.question_index for answer in self.answers]
        if len(indexes) != len(set(indexes)):
            raise ValueError("Duplicate question_index in answers payload")
        return self


class QuizQuestionResult(BaseModel):
    question_index: int
    selected_option_index: int | None
    correct_option_index: int
    is_correct: bool
    is_skipped: bool
    explanation: str


class QuizSubmitResponse(BaseModel):
    attempt_id: uuid.UUID
    quiz_id: uuid.UUID
    score: float
    total_questions: int
    correct_count: int
    incorrect_count: int
    skipped_count: int
    time_spent_seconds: int
    completed_at: datetime
    results: list[QuizQuestionResult]


class QuizAttemptListItemResponse(BaseModel):
    attempt_id: uuid.UUID
    quiz_id: uuid.UUID
    score: float
    total_questions: int
    time_spent_seconds: int
    completed_at: datetime
