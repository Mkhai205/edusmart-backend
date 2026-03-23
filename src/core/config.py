from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    # APP SETTINGS
    app_name: str = "EduSmart Backend"
    app_env: str = Field(default="development", alias="APP_ENV")
    api_prefix: str = "/api/v1"

    fastapi_host: str = Field(default="0.0.0.0", alias="FASTAPI_HOST")
    fastapi_port: int = Field(default=8000, alias="FASTAPI_PORT")
    # DATABASE SETTINGS
    database_url: str = Field(alias="DATABASE_URL")

    # MINIO SETTINGS
    minio_endpoint: str = Field(alias="MINIO_ENDPOINT")
    minio_access_key: str = Field(alias="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(alias="MINIO_SECRET_KEY")
    minio_secure: bool = Field(default=False, alias="MINIO_SECURE")
    minio_bucket_name: str = Field(default="edusmart-docs", alias="MINIO_BUCKET_NAME")

    # CORS SETTINGS
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    # GOOGLE OAUTH SETTINGS
    google_client_id: str = Field(alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = Field(alias="GOOGLE_REDIRECT_URI")

    # AI EMBEDDING SETTINGS
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    google_embeddings_model: str = Field(default="gemini-embedding-001", alias="GOOGLE_EMBEDDINGS_MODEL")
    embedding_dimension: int = Field(default=768, alias="EMBEDDING_DIMENSION")
    embedding_batch_size: int = Field(default=20, alias="EMBEDDING_BATCH_SIZE")
    embedding_max_retries: int = Field(default=2, alias="EMBEDDING_MAX_RETRIES")
    embedding_request_timeout_seconds: int = Field(default=60, alias="EMBEDDING_REQUEST_TIMEOUT_SECONDS")
    google_summary_model: str = Field(default="gemini-2.0-flash", alias="GOOGLE_SUMMARY_MODEL")
    summary_temperature: float = Field(default=0.2, alias="SUMMARY_TEMPERATURE")
    summary_max_tokens: int = Field(default=2048, alias="SUMMARY_MAX_TOKENS")
    summary_request_timeout_seconds: int = Field(default=90, alias="SUMMARY_REQUEST_TIMEOUT_SECONDS")
    summary_map_chunk_size: int = Field(default=12, alias="SUMMARY_MAP_CHUNK_SIZE")
    pixabay_api_key: str | None = Field(default=None, alias="PIXABAY_API_KEY")
    pixabay_base_url: str = Field(default="https://pixabay.com/api/", alias="PIXABAY_BASE_URL")
    pixabay_request_timeout_seconds: int = Field(default=10, alias="PIXABAY_REQUEST_TIMEOUT_SECONDS")

    frontend_login_success_redirect: str = Field(
        default="http://localhost:3000/auth/callback/success",
        alias="FRONTEND_LOGIN_SUCCESS_REDIRECT",
    )
    frontend_login_failure_redirect: str = Field(
        default="http://localhost:3000/auth/callback/error",
        alias="FRONTEND_LOGIN_FAILURE_REDIRECT",
    )

    # JWT SETTINGS
    jwt_secret_key: str = Field(alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=30, alias="REFRESH_TOKEN_EXPIRE_DAYS")

    access_cookie_name: str = Field(default="edusmart_access_token", alias="ACCESS_COOKIE_NAME")
    refresh_cookie_name: str = Field(default="edusmart_refresh_token", alias="REFRESH_COOKIE_NAME")
    oauth_state_cookie_name: str = Field(default="edusmart_oauth_state", alias="OAUTH_STATE_COOKIE_NAME")
    cookie_domain: str | None = Field(default=None, alias="COOKIE_DOMAIN")
    cookie_secure: bool = Field(default=False, alias="COOKIE_SECURE")
    cookie_samesite: str = Field(default="lax", alias="COOKIE_SAMESITE")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
