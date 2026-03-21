import asyncio
import math
import re
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
            all_pages_blocks: list[list[dict]] = []

            for page_number in range(1, total_pages + 1):
                page = document.load_page(page_number - 1)
                raw_blocks = page.get_text("blocks")
                page_height = float(page.rect.height)

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
                            "token_count": self._estimate_token_count(normalized_text),
                            "page_height": page_height,
                        }
                    )

                text_blocks.sort(key=lambda item: (item["bbox"][1], item["bbox"][0]))
                all_pages_blocks.append(text_blocks)

            filtered_pages_blocks = self._filter_repeated_header_footer(all_pages_blocks, total_pages)

            for page_number, page_blocks in enumerate(filtered_pages_blocks, start=1):
                page_chunks, chunk_index = self._merge_blocks_to_chunks(page_number, page_blocks, chunk_index)
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
        target_tokens_per_chunk = 400
        max_tokens_per_chunk = 500
        overlap_tokens = 100
        max_vertical_gap = 24.0

        chunks: list[dict] = []
        chunk_index = start_chunk_index
        start_idx = 0
        total_blocks = len(blocks)

        while start_idx < total_blocks:
            current_text_parts: list[str] = []
            current_bbox: list[float] | None = None
            current_tokens = 0
            end_idx = start_idx
            last_bottom: float | None = None

            while end_idx < total_blocks:
                block = blocks[end_idx]
                text = block["text"]
                bbox = block["bbox"]
                token_count = block.get("token_count") or self._estimate_token_count(text)

                vertical_gap = 0.0 if last_bottom is None else bbox[1] - last_bottom
                exceeds_token_budget = current_tokens + token_count > max_tokens_per_chunk
                should_split_for_gap = (
                    current_bbox is not None and vertical_gap > max_vertical_gap and current_tokens >= target_tokens_per_chunk // 2
                )

                if current_bbox is not None and (exceeds_token_budget or should_split_for_gap):
                    break

                current_text_parts.append(text)
                current_tokens += token_count
                if current_bbox is None:
                    current_bbox = bbox.copy()
                else:
                    current_bbox = [
                        min(current_bbox[0], bbox[0]),
                        min(current_bbox[1], bbox[1]),
                        max(current_bbox[2], bbox[2]),
                        max(current_bbox[3], bbox[3]),
                    ]

                last_bottom = bbox[3]
                end_idx += 1

                if current_tokens >= target_tokens_per_chunk and end_idx < total_blocks:
                    next_gap = blocks[end_idx]["bbox"][1] - last_bottom
                    if next_gap > max_vertical_gap * 0.75:
                        break

            if not current_text_parts:
                block = blocks[start_idx]
                current_text_parts = [block["text"]]
                current_bbox = block["bbox"].copy()
                current_tokens = block.get("token_count") or self._estimate_token_count(block["text"])
                end_idx = start_idx + 1

            merged_text = " ".join(current_text_parts).strip()
            if merged_text and current_bbox is not None:
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

            if end_idx >= total_blocks:
                break

            next_start_idx = end_idx
            overlap_accumulator = 0
            back_idx = end_idx - 1
            while back_idx > start_idx and overlap_accumulator < overlap_tokens:
                overlap_accumulator += blocks[back_idx].get("token_count") or self._estimate_token_count(blocks[back_idx]["text"])
                back_idx -= 1

            next_start_idx = max(back_idx + 1, start_idx + 1)
            start_idx = next_start_idx

        return chunks, chunk_index

    def _estimate_token_count(self, text: str) -> int:
        tokens = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
        return max(len(tokens), 1)

    def _normalize_template_text(self, text: str) -> str:
        lowered = text.lower()
        no_numbers = re.sub(r"\b\d+\b", "#", lowered)
        return re.sub(r"\s+", " ", no_numbers).strip()

    def _build_header_footer_key(self, block: dict) -> tuple[str, float, float, str] | None:
        page_height = block.get("page_height") or 0.0
        if page_height <= 0:
            return None

        x0, y0, x1, y1 = block["bbox"]
        del x0, x1
        top_threshold = page_height * 0.16
        bottom_threshold = page_height * 0.84

        zone: str | None
        if y1 <= top_threshold:
            zone = "header"
        elif y0 >= bottom_threshold:
            zone = "footer"
        else:
            return None

        token_count = block.get("token_count") or self._estimate_token_count(block["text"])
        if token_count > 25:
            return None

        normalized_text = self._normalize_template_text(block["text"])
        if len(normalized_text) < 4:
            return None

        relative_y0 = round(y0 / page_height, 2)
        relative_y1 = round(y1 / page_height, 2)
        return zone, relative_y0, relative_y1, normalized_text[:200]

    def _filter_repeated_header_footer(self, pages_blocks: list[list[dict]], total_pages: int) -> list[list[dict]]:
        if total_pages < 3:
            return pages_blocks

        page_hits: dict[tuple[str, float, float, str], set[int]] = {}
        for page_idx, blocks in enumerate(pages_blocks):
            seen_keys: set[tuple[str, float, float, str]] = set()
            for block in blocks:
                key = self._build_header_footer_key(block)
                if key is None:
                    continue
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                page_hits.setdefault(key, set()).add(page_idx)

        min_repeated_pages = max(2, math.ceil(total_pages * 0.6))
        repeated_keys = {key for key, pages in page_hits.items() if len(pages) >= min_repeated_pages}
        if not repeated_keys:
            return pages_blocks

        filtered_pages: list[list[dict]] = []
        for blocks in pages_blocks:
            filtered_pages.append(
                [
                    block
                    for block in blocks
                    if (self._build_header_footer_key(block) not in repeated_keys)
                ]
            )

        return filtered_pages

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
