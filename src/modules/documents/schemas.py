import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    document_id: uuid.UUID
    title: str
    file_url: str
    object_key: str
    content_type: str
    file_size: int
    total_pages: int | None
    is_public: bool
    created_at: datetime
    download_url: str


class DocumentDownloadResponse(BaseModel):
    document_id: uuid.UUID
    download_url: str
    expires_in_seconds: int
