import asyncio
import logging
import uuid

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from src.core.config import Settings
from src.models.document_chunk import DocumentChunk

logger = logging.getLogger("uvicorn.error")


class DocumentVectorizationService:
    def __init__(self, settings: Settings):
        self.settings = settings
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required to run document vectorization")
        self.primary_model = settings.google_embeddings_model
        self.fallback_models = [
            "gemini-embedding-001",
        ]

    async def embed_chunks(self, chunks: list[DocumentChunk]) -> dict[uuid.UUID, list[float]]:
        if not chunks:
            return {}

        texts = [self._normalize_text(chunk.text_content) for chunk in chunks]
        vectors = await self._embed_with_retry(texts)

        if len(vectors) != len(chunks):
            raise ValueError("Embedding output size mismatch")

        result: dict[uuid.UUID, list[float]] = {}
        for chunk, vector in zip(chunks, vectors, strict=True):
            if len(vector) != self.settings.embedding_dimension:
                raise ValueError(
                    f"Invalid embedding dimension for chunk {chunk.id}: "
                    f"expected {self.settings.embedding_dimension}, got {len(vector)}"
                )
            result[chunk.id] = vector

        return result

    async def _embed_with_retry(self, texts: list[str]) -> list[list[float]]:
        try:
            return await self._embed_with_retry_for_model(self.primary_model, texts)
        except Exception as exc:  # noqa: BLE001
            if not self._is_model_not_found_error(exc):
                error_detail = str(exc) if exc else "unknown error"
                raise RuntimeError(f"Failed to generate embeddings after retries: {error_detail}") from exc

            tried = [self.primary_model]
            for fallback_model in self.fallback_models:
                if fallback_model == self.primary_model:
                    continue

                logger.warning(
                    "Embedding model %s not found/unsupported, trying fallback %s",
                    tried[-1],
                    fallback_model,
                )
                try:
                    return await self._embed_with_retry_for_model(fallback_model, texts)
                except Exception as fallback_exc:  # noqa: BLE001
                    tried.append(fallback_model)
                    if not self._is_model_not_found_error(fallback_exc):
                        error_detail = str(fallback_exc) if fallback_exc else "unknown error"
                        raise RuntimeError(f"Failed to generate embeddings after retries: {error_detail}") from fallback_exc

            raise RuntimeError(
                "Failed to generate embeddings after retries: no compatible embedding model found. "
                f"tried={tried}"
            ) from exc

    async def _embed_with_retry_for_model(self, model: str, texts: list[str]) -> list[list[float]]:
        attempts = self.settings.embedding_max_retries + 1
        backoff_seconds = 1.0
        last_error: Exception | None = None
        client = GoogleGenerativeAIEmbeddings(
            model=model,
            api_key=self.settings.gemini_api_key,
            output_dimensionality=self.settings.embedding_dimension,
        )

        for attempt in range(1, attempts + 1):
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(client.embed_documents, texts),
                    timeout=self.settings.embedding_request_timeout_seconds,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt >= attempts:
                    break
                await asyncio.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2, 8.0)

        error_detail = str(last_error) if last_error else "unknown error"
        raise RuntimeError(f"model={model}, detail={error_detail}") from last_error

    def _is_model_not_found_error(self, exc: Exception) -> bool:
        message = str(exc).upper()
        return "NOT_FOUND" in message or "IS NOT FOUND" in message or "NOT SUPPORTED FOR EMBEDCONTENT" in message

    def _normalize_text(self, value: str) -> str:
        normalized = " ".join(value.split()).strip()
        return normalized or "[empty]"
