import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ExtractionStatus = Literal["pending", "processing", "completed", "failed"]


class DocumentUploadResponse(BaseModel):
    document_id: uuid.UUID
    title: str
    file_url: str
    object_key: str
    content_type: str
    file_size: int
    total_pages: int | None
    is_public: bool
    extraction_status: ExtractionStatus
    created_at: datetime
    download_url: str


class DocumentDownloadResponse(BaseModel):
    document_id: uuid.UUID
    download_url: str
    expires_in_seconds: int


class DocumentExtractionStatusResponse(BaseModel):
    document_id: uuid.UUID
    extraction_status: ExtractionStatus
    total_pages: int | None
    extraction_error: str | None
    extracted_at: datetime | None


class SemanticSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=5000)
    limit: int = Field(default=5, ge=1, le=20)
    min_similarity: float = Field(default=0.0, ge=0.0, le=1.0)


class SemanticSearchChunkResult(BaseModel):
    chunk_id: uuid.UUID
    page_number: int
    chunk_index: int
    text_content: str
    bbox: list[float] | None
    element_type: str
    similarity: float


class SemanticSearchResponse(BaseModel):
    document_id: uuid.UUID
    query: str
    results: list[SemanticSearchChunkResult]
