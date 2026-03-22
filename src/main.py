import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import get_settings
from src.modules.auth.router import router as auth_router
from src.modules.documents.router import router as documents_router
from src.modules.summaries.router import router as summaries_router

settings = get_settings()
logger = logging.getLogger("uvicorn.error")


def _docs_base_url() -> str:
    return f"http://{settings.fastapi_host}:{settings.fastapi_port}"


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    @app.on_event("startup")
    async def log_docs_urls() -> None:
        base_url = _docs_base_url()
        logger.info("Swagger UI: %s/docs", base_url)
        logger.info("ReDoc: %s/redoc", base_url)
        logger.info("OpenAPI JSON: %s/openapi.json", base_url)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", tags=["system"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth_router, prefix=settings.api_prefix)
    app.include_router(documents_router, prefix=settings.api_prefix)
    app.include_router(summaries_router, prefix=settings.api_prefix)
    return app


app = create_app()
