import uuid
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class SummaryMode(str, Enum):
    FULL_MAP_REDUCE = "full_map_reduce"
    PAGE_RANGE = "page_range"
    KEYWORD_HYBRID = "keyword_hybrid"


SummaryStatus = Literal["pending", "processing", "completed", "failed"]


class DocumentSummaryRequest(BaseModel):
    mode: SummaryMode
    start_page: int | None = Field(default=None, ge=1)
    end_page: int | None = Field(default=None, ge=1)
    keywords: list[str] | None = Field(default=None, min_length=1, max_length=100)
    search_limit: int = Field(default=5, ge=1, le=30)
    min_similarity: float = Field(default=0.2, ge=0.0, le=1.0)


class SummarySourceChunk(BaseModel):
    chunk_id: uuid.UUID
    page_number: int
    chunk_index: int
    bbox: list[float] | None
    similarity: float | None = None


class DocumentSummaryQueuedResponse(BaseModel):
    summary_id: uuid.UUID
    document_id: uuid.UUID
    summary_status: SummaryStatus
    mode: SummaryMode
    options: dict
    created_at: datetime


class DocumentSummaryStatusResponse(BaseModel):
    summary_id: uuid.UUID
    document_id: uuid.UUID
    summary_status: SummaryStatus
    mode: SummaryMode
    options: dict
    # Frontend renders this content with react-markdown.
    content_markdown: str | None
    summary_error: str | None
    share_token: str | None
    sources: list[SummarySourceChunk] | None = None
    completed_at: datetime | None
    created_at: datetime
