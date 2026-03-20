import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


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
