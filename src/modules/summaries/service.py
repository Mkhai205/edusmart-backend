import uuid
from fastapi import HTTPException, status
from langchain_google_genai import ChatGoogleGenerativeAI
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.infrastructure.database.session import AsyncSessionFactory
from src.models.document_chunk import DocumentChunk
from src.models.summary import Summary
from src.models.user import User
from src.modules.documents.vectorization_service import DocumentVectorizationService
from src.modules.summaries.repository import SummariesRepository
from src.modules.summaries.schemas import (
    DocumentSummaryQueuedResponse,
    DocumentSummaryStatusResponse,
    SummaryMode,
)


class SummariesService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SummariesRepository(session)

    async def queue_summary_generation(
        self,
        *,
        document_id: uuid.UUID,
        mode: SummaryMode,
        current_user: User,
        start_page: int | None,
        end_page: int | None,
        keywords: list[str] | None,
        search_limit: int,
        min_similarity: float,
    ) -> DocumentSummaryQueuedResponse:
        document = await self.repo.get_user_document(document_id=document_id, user_id=current_user.id)
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

        if document.extraction_status != "completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Document extraction/vectorization is not completed yet",
            )

        settings = get_settings()
        if not settings.gemini_api_key:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="GEMINI_API_KEY is not configured")

        options = self._build_summary_options(
            document_total_pages=document.total_pages,
            mode=mode,
            start_page=start_page,
            end_page=end_page,
            keywords=keywords,
            search_limit=search_limit,
            min_similarity=min_similarity,
        )

        summary = await self.repo.create_summary(
            document_id=document_id,
            user_id=current_user.id,
            mode=mode.value,
            options=options,
            content_markdown="",
            share_token=None,
        )
        await self.session.commit()

        return DocumentSummaryQueuedResponse(
            summary_id=summary.id,
            document_id=document_id,
            summary_status=summary.summary_status,
            mode=mode,
            options=options,
            created_at=summary.created_at,
        )

    async def get_summary_status(
        self,
        *,
        document_id: uuid.UUID,
        summary_id: uuid.UUID,
        current_user: User,
    ) -> DocumentSummaryStatusResponse:
        summary = await self.repo.get_user_summary(
            summary_id=summary_id,
            document_id=document_id,
            user_id=current_user.id,
        )
        if summary is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Summary not found")

        return DocumentSummaryStatusResponse(
            summary_id=summary.id,
            document_id=summary.document_id,
            summary_status=summary.summary_status,
            mode=SummaryMode(summary.mode),
            options=summary.options or {},
            content_markdown=summary.content_markdown if summary.summary_status == "completed" else None,
            summary_error=summary.summary_error,
            share_token=summary.share_token,
            sources=None,
            completed_at=summary.completed_at,
            created_at=summary.created_at,
        )

    @staticmethod
    async def run_summary_pipeline(summary_id: uuid.UUID) -> None:
        async with AsyncSessionFactory() as session:
            service = SummariesService(session=session)
            await service._run_summary_pipeline(summary_id)

    async def _run_summary_pipeline(self, summary_id: uuid.UUID) -> None:
        settings = get_settings()
        summary = await self.repo.get_summary_by_id(summary_id)
        if summary is None:
            return

        await self.repo.update_summary_status(summary_id=summary_id, status_value="processing", summary_error=None)
        await self.session.commit()

        try:
            content_markdown = await self._generate_summary_content(summary=summary, settings=settings)
            summary.content_markdown = content_markdown
            await self.repo.update_summary_status(summary_id=summary_id, status_value="completed", summary_error=None)
            await self.session.commit()
        except Exception as exc:  # noqa: BLE001
            await self.session.rollback()
            await self.repo.update_summary_status(
                summary_id=summary_id,
                status_value="failed",
                summary_error=str(exc)[:1000],
            )
            await self.session.commit()

    async def _generate_summary_content(self, *, summary: Summary, settings) -> str:
        mode = SummaryMode(summary.mode)
        options = summary.options or {}
        keywords = options.get("keywords") if isinstance(options, dict) else None

        chunks = await self._collect_chunks_for_summary(
            document_id=summary.document_id,
            mode=mode,
            options=options,
            settings=settings,
        )
        if not chunks:
            raise RuntimeError("No embedded chunks matched the summary request")

        return await self._summarize_chunks_to_markdown(
            settings=settings,
            mode=mode,
            chunks=chunks,
            keywords=keywords if isinstance(keywords, list) else None,
        )

    async def _collect_chunks_for_summary(
        self,
        *,
        document_id: uuid.UUID,
        mode: SummaryMode,
        options: dict,
        settings,
    ) -> list[DocumentChunk]:
        if mode == SummaryMode.FULL_MAP_REDUCE:
            return await self.repo.get_all_embedded_chunks(document_id)

        if mode == SummaryMode.PAGE_RANGE:
            start_page = int(options.get("start_page", 0))
            end_page = int(options.get("end_page", 0))
            if start_page <= 0 or end_page <= 0:
                raise RuntimeError("Invalid page_range options")
            return await self.repo.get_embedded_chunks_by_page_range(
                document_id=document_id,
                start_page=start_page,
                end_page=end_page,
            )

        keywords = options.get("keywords") or []
        search_limit = int(options.get("search_limit", 5))
        min_similarity = float(options.get("min_similarity", 0.2))
        if not isinstance(keywords, list) or not keywords:
            raise RuntimeError("Invalid keyword_hybrid options")

        vectorization_service = DocumentVectorizationService(settings)
        merged: dict[uuid.UUID, tuple[DocumentChunk, float]] = {}
        for keyword in keywords:
            query_embedding = await vectorization_service.embed_query(str(keyword))
            rows = await self.repo.semantic_search_chunks(
                document_id=document_id,
                query_embedding=query_embedding,
                limit=search_limit,
                min_similarity=min_similarity,
            )
            for chunk, similarity in rows:
                existing = merged.get(chunk.id)
                if existing is None or similarity > existing[1]:
                    merged[chunk.id] = (chunk, similarity)

        sorted_rows = sorted(merged.values(), key=lambda item: item[1], reverse=True)
        return [item[0] for item in sorted_rows]

    def _build_summary_options(
        self,
        *,
        document_total_pages: int | None,
        mode: SummaryMode,
        start_page: int | None,
        end_page: int | None,
        keywords: list[str] | None,
        search_limit: int,
        min_similarity: float,
    ) -> dict[str, object]:
        options: dict[str, object] = {"mode": mode.value}

        if mode == SummaryMode.FULL_MAP_REDUCE:
            return options

        if mode == SummaryMode.PAGE_RANGE:
            if start_page is None or end_page is None:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="start_page and end_page are required")
            if start_page > end_page:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="start_page must be <= end_page")
            if document_total_pages is not None and end_page > document_total_pages:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"end_page exceeds total pages ({document_total_pages})",
                )
            options.update({"start_page": start_page, "end_page": end_page})
            return options

        cleaned_keywords = [kw.strip() for kw in (keywords or []) if kw.strip()]
        if not cleaned_keywords:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="keywords are required for keyword_hybrid")
        options.update(
            {
                "keywords": cleaned_keywords,
                "search_limit": search_limit,
                "min_similarity": min_similarity,
            }
        )
        return options

    async def _summarize_chunks_to_markdown(
        self,
        *,
        settings,
        mode: SummaryMode,
        chunks: list[DocumentChunk],
        keywords: list[str] | None,
    ) -> str:
        map_chunk_size = max(1, settings.summary_map_chunk_size)
        llm = ChatGoogleGenerativeAI(
            model=settings.google_summary_model,
            api_key=settings.gemini_api_key,
            temperature=settings.summary_temperature,
            request_timeout=settings.summary_request_timeout_seconds,
        )

        context_blocks = [self._format_chunk_for_prompt(chunk) for chunk in chunks]

        if len(context_blocks) <= map_chunk_size:
            return await self._invoke_summary_llm(
                llm=llm,
                system_prompt=self._summary_system_prompt(),
                user_prompt=self._build_summary_user_prompt(mode=mode, contexts=context_blocks, keywords=keywords),
            )

        partial_summaries: list[str] = []
        for start in range(0, len(context_blocks), map_chunk_size):
            batch_contexts = context_blocks[start : start + map_chunk_size]
            partial = await self._invoke_summary_llm(
                llm=llm,
                system_prompt=self._summary_system_prompt(),
                user_prompt=self._build_map_prompt(mode=mode, contexts=batch_contexts),
            )
            partial_summaries.append(partial)

        return await self._invoke_summary_llm(
            llm=llm,
            system_prompt=self._summary_system_prompt(),
            user_prompt=self._build_reduce_prompt(mode=mode, partial_summaries=partial_summaries, keywords=keywords),
        )

    async def _invoke_summary_llm(self, *, llm: ChatGoogleGenerativeAI, system_prompt: str, user_prompt: str) -> str:
        response = await llm.ainvoke([
            ("system", system_prompt),
            ("human", user_prompt),
        ])
        content = getattr(response, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and "text" in item:
                    parts.append(str(item["text"]))
            return "\n".join(parts)
        return str(content)

    def _summary_system_prompt(self) -> str:
        return (
            "[VAI TRÒ CỦA BẠN]\n"
            "Bạn là EduSmart - một Gia sư AI thông minh, tận tâm và có chuyên môn cao, hỗ trợ sinh viên học thuật.\n\n"
            "[QUY TẮC ĐỊNH DẠNG BẮT BUỘC - TUÂN THỦ 100%]\n"
            "1. CHỈ dùng Markdown. Không dùng HTML thô để định dạng văn bản thông thường.\n"
            "2. Công thức Toán/Lý/Hóa phải dùng LaTeX: inline dùng $...$, block dùng $$...$$.\n"
            "3. Không bịa đặt: nếu tài liệu không có thông tin, nói rõ 'Tài liệu hiện tại không chứa thông tin này.'.\n\n"
            "[YÊU CẦU TẠO TƯƠNG TÁC & BIỂU ĐỒ]\n"
            "Chỉ khi thật sự cần biểu đồ/mô phỏng mới tạo 1 khối mã ```html ... ``` hoàn chỉnh, tự chứa, có thể dùng CDN "
            "(ưu tiên Chart.js, D3.js hoặc p5.js). Không dùng HTML ngoài code block."
        )

    def _build_summary_user_prompt(self, *, mode: SummaryMode, contexts: list[str], keywords: list[str] | None) -> str:
        keyword_line = ""
        if keywords:
            keyword_line = f"\nTừ khóa ưu tiên: {', '.join(keywords)}"

        return (
            f"Chế độ tóm tắt: {mode.value}.{keyword_line}\n"
            "Dựa trên context dưới đây, tạo bản tóm tắt Markdown gồm: tiêu đề, overview, ý chính, "
            "kiến thức cần nhớ, kết luận, bảng tóm tắt nhanh.\n"
            "Ưu tiên ngắn gọn, rõ ràng, dễ đọc trên mobile/desktop.\n"
            "Context:\n"
            f"{'\n\n'.join(contexts)}"
        )

    def _build_map_prompt(self, *, mode: SummaryMode, contexts: list[str]) -> str:
        return (
            f"Chế độ tóm tắt: {mode.value}.\n"
            "Tạo tóm tắt Markdown cho nhóm context sau. Tập trung facts quan trọng và thuật ngữ chính.\n"
            "Context batch:\n"
            f"{'\n\n'.join(contexts)}"
        )

    def _build_reduce_prompt(self, *, mode: SummaryMode, partial_summaries: list[str], keywords: list[str] | None) -> str:
        keyword_line = ""
        if keywords:
            keyword_line = f"\nTừ khóa ưu tiên: {', '.join(keywords)}"

        return (
            f"Chế độ tóm tắt: {mode.value}.{keyword_line}\n"
            "Gộp các bản tóm tắt Markdown sau thành một bản Markdown cuối cùng, "
            "loại bỏ trùng lặp, giữ mạch logic học tập.\n"
            "Partial summaries:\n"
            f"{'\n\n'.join(partial_summaries)}"
        )

    def _format_chunk_for_prompt(self, chunk: DocumentChunk) -> str:
        return f"[page={chunk.page_number}, chunk={chunk.chunk_index}] {chunk.text_content}"
