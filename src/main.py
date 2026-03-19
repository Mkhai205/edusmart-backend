from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import get_settings
from src.modules.auth.router import router as auth_router

settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

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
    return app


app = create_app()
