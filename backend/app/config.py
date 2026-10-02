"""Environment-backed application settings."""

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated settings shared by the API and its services."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    environment: str = Field(default="development", alias="CODELENS_ENV")
    host: str = Field(default="127.0.0.1", alias="CODELENS_HOST")
    port: Annotated[int, Field(ge=1, le=65535, alias="CODELENS_PORT")] = 8000
    temp_root: str | None = Field(default=None, alias="CODELENS_TEMP_ROOT")
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173"], alias="CORS_ORIGINS"
    )

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_chat_model: str | None = Field(default=None, alias="OPENAI_CHAT_MODEL")

    embedding_provider: str = Field(default="fake", alias="CODELENS_EMBEDDING_PROVIDER")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_embedding_model: str = Field(
        default="gemini-embedding-001", alias="GEMINI_EMBEDDING_MODEL"
    )
    embedding_dimensions: int = Field(default=8, ge=1, le=3072, alias="EMBEDDING_DIMENSIONS")
    embedding_batch_size: int = Field(default=32, ge=1, le=1000, alias="EMBEDDING_BATCH_SIZE")
    embedding_timeout: float = Field(default=30.0, gt=0, le=300, alias="EMBEDDING_TIMEOUT")
    embedding_max_retries: int = Field(default=2, ge=0, le=5, alias="EMBEDDING_MAX_RETRIES")
    embedding_retry_backoff: float = Field(
        default=0.25, ge=0, le=10, alias="EMBEDDING_RETRY_BACKOFF"
    )

    openai_embedding_model: str | None = Field(default=None, alias="OPENAI_EMBEDDING_MODEL")
    openai_embedding_dimensions: int | None = Field(
        default=None, ge=1, alias="OPENAI_EMBEDDING_DIMENSIONS"
    )

    @field_validator("embedding_provider")
    @classmethod
    def validate_embedding_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"fake", "gemini"}:
            raise ValueError("embedding provider must be fake or gemini")
        return normalized

    @field_validator("gemini_embedding_model")
    @classmethod
    def validate_embedding_model(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Gemini embedding model must not be empty")
        return normalized

    max_repository_bytes: int = Field(
        default=100 * 1024 * 1024, ge=1, alias="CODELENS_MAX_REPOSITORY_BYTES"
    )
    max_extracted_bytes: int = Field(
        default=500 * 1024 * 1024, ge=1, alias="CODELENS_MAX_EXTRACTED_BYTES"
    )
    max_extracted_files: int = Field(default=10_000, ge=1, alias="CODELENS_MAX_EXTRACTED_FILES")
    max_archive_path_length: int = Field(
        default=512, ge=1, alias="CODELENS_MAX_ARCHIVE_PATH_LENGTH"
    )
    max_archive_nesting: int = Field(default=100, ge=1, alias="CODELENS_MAX_ARCHIVE_NESTING")
    max_file_bytes: int = Field(default=10 * 1024 * 1024, ge=1, alias="CODELENS_MAX_FILE_BYTES")
    ignored_directories: frozenset[str] = Field(
        default=frozenset(
            {".git", "node_modules", ".venv", "dist", "build", "coverage", "__pycache__"}
        ),
        alias="CODELENS_IGNORED_DIRECTORIES",
    )
    max_discovered_files: int = Field(default=10_000, ge=1, alias="CODELENS_MAX_DISCOVERED_FILES")
    max_discovered_bytes: int = Field(
        default=500 * 1024 * 1024, ge=1, alias="CODELENS_MAX_DISCOVERED_BYTES"
    )
    top_k: int = Field(default=8, ge=1, le=100, alias="CODELENS_TOP_K")

    @field_validator("ignored_directories", mode="before")
    @classmethod
    def parse_ignored_directories(cls, value: str | frozenset[str] | list[str]) -> frozenset[str]:
        if isinstance(value, str):
            return frozenset(part.strip() for part in value.split(",") if part.strip())
        return frozenset(value)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Return one validated settings instance for the process."""

    return Settings()
