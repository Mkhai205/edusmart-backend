import asyncio
from dataclasses import dataclass
from io import BytesIO

import fitz
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer

from src.infrastructure.storage.minio_client import MinioStorageClient


@dataclass
class ExtractedChunk:
    page_number: int
    chunk_index: int
    text_content: str
    bbox: list[float] | None
    element_type: str


class DocumentExtractionService:
    def __init__(self, minio_client: MinioStorageClient):
        self.minio_client = minio_client

    async def extract_from_object(self, object_key: str) -> tuple[int, list[dict]]:
        pdf_bytes = await self.minio_client.download_bytes(object_key)
        try:
            return await asyncio.to_thread(self._extract_with_pymupdf, pdf_bytes)
        except ModuleNotFoundError:
            return await asyncio.to_thread(self._extract_with_pdfminer, pdf_bytes)

    def _extract_with_pymupdf(self, pdf_bytes: bytes) -> tuple[int, list[dict]]:
        chunks: list[dict] = []
        chunk_index = 0
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            total_pages = document.page_count

            for page_number in range(1, total_pages + 1):
                page = document.load_page(page_number - 1)
                raw_blocks = page.get_text("blocks")

                text_blocks = []
                for block in raw_blocks:
                    if len(block) < 5:
                        continue

                    x0, y0, x1, y1, text = block[:5]
                    normalized_text = " ".join((text or "").split())
                    if not normalized_text:
                        continue

                    text_blocks.append(
                        {
                            "bbox": [float(x0), float(y0), float(x1), float(y1)],
                            "text": normalized_text,
                        }
                    )

                text_blocks.sort(key=lambda item: (item["bbox"][1], item["bbox"][0]))
                page_chunks, chunk_index = self._merge_blocks_to_chunks(page_number, text_blocks, chunk_index)
                chunks.extend(page_chunks)

            return total_pages, chunks
        finally:
            document.close()

    def _merge_blocks_to_chunks(
        self,
        page_number: int,
        blocks: list[dict],
        start_chunk_index: int,
    ) -> tuple[list[dict], int]:
        max_chars_per_chunk = 900
        max_vertical_gap = 24.0

        chunks: list[dict] = []
        chunk_index = start_chunk_index
        current_text_parts: list[str] = []
        current_bbox: list[float] | None = None

        for block in blocks:
            text = block["text"]
            bbox = block["bbox"]

            if current_bbox is None:
                current_text_parts = [text]
                current_bbox = bbox.copy()
                continue

            projected_length = len(" ".join(current_text_parts)) + 1 + len(text)
            vertical_gap = bbox[1] - current_bbox[3]
            should_split = projected_length > max_chars_per_chunk or vertical_gap > max_vertical_gap

            if should_split:
                merged_text = " ".join(current_text_parts).strip()
                if merged_text:
                    chunk = ExtractedChunk(
                        page_number=page_number,
                        chunk_index=chunk_index,
                        text_content=merged_text,
                        bbox=current_bbox,
                        element_type="TextBlockGroup",
                    )
                    chunks.append(
                        {
                            "page_number": chunk.page_number,
                            "chunk_index": chunk.chunk_index,
                            "text_content": chunk.text_content,
                            "bbox": chunk.bbox,
                            "element_type": chunk.element_type,
                        }
                    )
                    chunk_index += 1

                current_text_parts = [text]
                current_bbox = bbox.copy()
                continue

            current_text_parts.append(text)
            current_bbox = [
                min(current_bbox[0], bbox[0]),
                min(current_bbox[1], bbox[1]),
                max(current_bbox[2], bbox[2]),
                max(current_bbox[3], bbox[3]),
            ]

        if current_bbox is not None:
            merged_text = " ".join(current_text_parts).strip()
            if merged_text:
                chunk = ExtractedChunk(
                    page_number=page_number,
                    chunk_index=chunk_index,
                    text_content=merged_text,
                    bbox=current_bbox,
                    element_type="TextBlockGroup",
                )
                chunks.append(
                    {
                        "page_number": chunk.page_number,
                        "chunk_index": chunk.chunk_index,
                        "text_content": chunk.text_content,
                        "bbox": chunk.bbox,
                        "element_type": chunk.element_type,
                    }
                )
                chunk_index += 1

        return chunks, chunk_index

    def _extract_with_pdfminer(self, pdf_bytes: bytes) -> tuple[int, list[dict]]:
        chunks: list[dict] = []
        max_page = 0
        chunk_index = 0

        for page_number, page_layout in enumerate(extract_pages(BytesIO(pdf_bytes)), start=1):
            max_page = max(max_page, page_number)
            for layout in page_layout:
                if not isinstance(layout, LTTextContainer):
                    continue

                text = " ".join((layout.get_text() or "").split()).strip()
                if not text:
                    continue

                x0, y0, x1, y1 = layout.bbox
                chunk = ExtractedChunk(
                    page_number=page_number,
                    chunk_index=chunk_index,
                    text_content=text,
                    bbox=[float(x0), float(y0), float(x1), float(y1)],
                    element_type="TextContainer",
                )
                chunks.append(
                    {
                        "page_number": chunk.page_number,
                        "chunk_index": chunk.chunk_index,
                        "text_content": chunk.text_content,
                        "bbox": chunk.bbox,
                        "element_type": chunk.element_type,
                    }
                )
                chunk_index += 1

        return max_page, chunks
