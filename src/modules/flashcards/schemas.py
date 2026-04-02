import uuid
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class FlashcardSetStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class FlashcardAlgorithm(str, Enum):
    CUSTOM_V1 = "custom_v1"


class FlashcardType(str, Enum):
    TERM_DEFINITION = "term_definition"
    QA = "qa"
    CLOZE = "cloze"


class FlashcardReviewRating(str, Enum):
    HARD = "hard"
    MEDIUM = "medium"
    EASY = "easy"


FlashcardSetStatusLiteral = Literal["pending", "processing", "completed", "failed"]


class FlashcardGenerateRequest(BaseModel):
    document_id: uuid.UUID
    title: str | None = Field(default=None, min_length=1, max_length=255)
    card_count: int = Field(default=20, ge=5, le=100)
    algorithm: FlashcardAlgorithm = FlashcardAlgorithm.CUSTOM_V1
    start_page: int | None = Field(default=None, ge=1)
    end_page: int | None = Field(default=None, ge=1)
    include_images: bool = True

    @model_validator(mode="after")
    def validate_page_range(self) -> "FlashcardGenerateRequest":
        if (self.start_page is None) != (self.end_page is None):
            raise ValueError("start_page and end_page must be provided together")
        if self.start_page is not None and self.end_page is not None and self.start_page > self.end_page:
            raise ValueError("start_page must be less than or equal to end_page")
        return self


class FlashcardQueuedResponse(BaseModel):
    set_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    generation_status: FlashcardSetStatusLiteral
    card_count_requested: int
    algorithm: FlashcardAlgorithm
    created_at: datetime


class FlashcardSetListItemResponse(BaseModel):
    set_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    algorithm: str | None
    generation_status: FlashcardSetStatusLiteral
    card_count: int
    completed_at: datetime | None
    created_at: datetime


class FlashcardSetDetailResponse(BaseModel):
    set_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    algorithm: str | None
    generation_status: FlashcardSetStatusLiteral
    generation_error: str | None
    card_count: int
    options: dict | None
    completed_at: datetime | None
    created_at: datetime


class FlashcardItemResponse(BaseModel):
    card_id: uuid.UUID
    set_id: uuid.UUID
    card_type: FlashcardType
    front: str
    back: str
    image_url: str | None
    image_keyword: str | None
    ease_factor: float | None
    interval_days: int | None
    repetitions: int
    next_review_at: datetime | None
    last_rating: FlashcardReviewRating | None


class FlashcardReviewTodayResponse(BaseModel):
    card_id: uuid.UUID
    set_id: uuid.UUID
    set_title: str
    card_type: FlashcardType
    front: str
    back: str
    image_url: str | None
    image_keyword: str | None
    ease_factor: float | None
    interval_days: int | None
    repetitions: int
    next_review_at: datetime
    last_rating: FlashcardReviewRating | None


class FlashcardReviewRequest(BaseModel):
    rating: FlashcardReviewRating


class FlashcardReviewResponse(BaseModel):
    card_id: uuid.UUID
    rating: FlashcardReviewRating
    ease_factor: float
    interval_days: int
    repetitions: int
    next_review_at: datetime


class ManualFlashcardSetCreateRequest(BaseModel):
    document_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)


class ManualFlashcardSetUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class ManualFlashcardSetResponse(BaseModel):
    set_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    algorithm: str | None
    generation_status: FlashcardSetStatusLiteral
    card_count: int
    completed_at: datetime | None
    created_at: datetime


class ManualFlashcardCardCreateRequest(BaseModel):
    card_type: FlashcardType = FlashcardType.TERM_DEFINITION
    front: str = Field(min_length=1)
    back: str = Field(min_length=1)
    image_url: str | None = None
    image_keyword: str | None = None


class ManualFlashcardCardUpdateRequest(BaseModel):
    card_type: FlashcardType | None = None
    front: str | None = Field(default=None, min_length=1)
    back: str | None = Field(default=None, min_length=1)
    image_url: str | None = None
    image_keyword: str | None = None
