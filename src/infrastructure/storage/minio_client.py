import asyncio
import io
from datetime import timedelta

from fastapi import HTTPException, status
from minio import Minio
from minio.error import S3Error

from src.core.config import get_settings

settings = get_settings()


class MinioStorageClient:
    def __init__(self) -> None:
        self.bucket_name = settings.minio_bucket_name
        self._client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self._bucket_ready = False
        self._bucket_lock = asyncio.Lock()

    async def _ensure_bucket(self) -> None:
        if self._bucket_ready:
            return

        async with self._bucket_lock:
            if self._bucket_ready:
                return

            try:
                exists = await asyncio.to_thread(self._client.bucket_exists, self.bucket_name)
                if not exists:
                    await asyncio.to_thread(self._client.make_bucket, self.bucket_name)
                self._bucket_ready = True
            except S3Error as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Storage service unavailable",
                ) from exc

    async def upload_bytes(self, object_key: str, content: bytes, content_type: str) -> None:
        await self._ensure_bucket()

        try:
            stream = io.BytesIO(content)
            await asyncio.to_thread(
                self._client.put_object,
                self.bucket_name,
                object_key,
                stream,
                len(content),
                content_type=content_type,
            )
        except S3Error as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to upload file to storage",
            ) from exc

    async def download_bytes(self, object_key: str) -> bytes:
        await self._ensure_bucket()

        try:
            response = await asyncio.to_thread(self._client.get_object, self.bucket_name, object_key)
            try:
                return await asyncio.to_thread(response.read)
            finally:
                response.close()
                response.release_conn()
        except S3Error as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found in storage",
            ) from exc

    async def generate_download_url(self, object_key: str, expires_seconds: int = 900) -> str:
        await self._ensure_bucket()

        try:
            return await asyncio.to_thread(
                self._client.presigned_get_object,
                self.bucket_name,
                object_key,
                timedelta(seconds=expires_seconds),
            )
        except S3Error as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to generate download URL",
            ) from exc

    def build_file_url(self, object_key: str) -> str:
        scheme = "https" if settings.minio_secure else "http"
        return f"{scheme}://{settings.minio_endpoint}/{self.bucket_name}/{object_key}"

    async def delete_object(self, object_key: str) -> None:
        await self._ensure_bucket()

        try:
            await asyncio.to_thread(self._client.remove_object, self.bucket_name, object_key)
        except S3Error:
            # Best-effort cleanup path; do not mask the original upload flow errors.
            return
