"""Construct configured embedding providers."""

from ..config import Settings
from .fake import FakeEmbeddings
from .gemini import GeminiEmbeddings
from .protocol import EmbeddingProvider


def create_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """Build the configured provider without exposing vendor details to callers."""
    if settings.embedding_provider == "fake":
        return FakeEmbeddings(settings.embedding_dimensions)
    if settings.embedding_provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required for the Gemini provider")
        return GeminiEmbeddings(
            api_key=settings.gemini_api_key,
            model=settings.gemini_embedding_model,
            dimensions=settings.embedding_dimensions,
            batch_size=settings.embedding_batch_size,
            timeout=settings.embedding_timeout,
            max_retries=settings.embedding_max_retries,
            backoff=settings.embedding_retry_backoff,
        )
    raise ValueError(f"unsupported embedding provider: {settings.embedding_provider}")
