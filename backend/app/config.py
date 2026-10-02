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
    openai_embedding_model: str | None = Field(default=None, alias="OPENAI_EMBEDDING_MODEL")
    openai_embedding_dimensions: int | None = Field(
        default=None, ge=1, alias="OPENAI_EMBEDDING_DIMENSIONS"
    )

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
