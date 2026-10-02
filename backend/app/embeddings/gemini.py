"""Google Gemini embedding adapter."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from typing import Any

from .protocol import EmbeddingProviderError, Vector


class GeminiEmbeddings:
    """Batching, validation, and bounded retry around a Gemini client."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimensions: int,
        batch_size: int = 32,
        timeout: float = 30.0,
        max_retries: int = 2,
        backoff: float = 0.25,
        client: Any | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key:
            raise ValueError("Gemini API key is required")
        if dimensions < 1 or batch_size < 1 or timeout <= 0 or max_retries < 0 or backoff < 0:
            raise ValueError("invalid Gemini embedding configuration")
        self.dimensions = dimensions
        self.model = model
        self.batch_size = batch_size
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        self._sleep = sleep
        self._client = client or self._build_client(api_key)

    @staticmethod
    def _build_client(api_key: str) -> Any:
        try:
            from google import genai  # type: ignore[import-not-found]
        except ImportError as error:
            raise EmbeddingProviderError("Gemini provider dependency is not installed") from error
        return genai.Client(api_key=api_key)

    def embed_query(self, text: str) -> Vector:
        """Embed one query using the same provider contract as documents."""
        return self.embed_documents([text])[0]

    def embed_documents(self, texts: Sequence[str]) -> list[Vector]:
        """Embed texts in bounded batches while preserving order."""
        if not texts:
            raise EmbeddingProviderError("at least one text is required")
        values = list(texts)
        vectors: list[Vector] = []
        for start in range(0, len(values), self.batch_size):
            vectors.extend(self._embed_batch(values[start : start + self.batch_size]))
        return vectors

    def _embed_batch(self, texts: Sequence[str]) -> list[Vector]:
        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.models.embed_content(
                    model=self.model,
                    contents=list(texts),
                    config={"output_dimensionality": self.dimensions},
                )
                return self._parse_response(response, len(texts))
            except EmbeddingProviderError:
                raise
            except Exception as error:
                if attempt >= self.max_retries or not self._is_transient(error):
                    raise EmbeddingProviderError("Gemini embedding request failed") from error
                self._sleep(min(self.backoff * (2**attempt), 4.0))
        raise AssertionError("retry loop must return or raise")

    def _parse_response(self, response: Any, expected: int) -> list[Vector]:
        raw = getattr(response, "embeddings", None)
        if raw is None:
            raise EmbeddingProviderError("Gemini returned no embeddings")
        vectors = [list(getattr(item, "values", ())) for item in raw]
        if len(vectors) != expected or any(len(vector) != self.dimensions for vector in vectors):
            raise EmbeddingProviderError("Gemini returned invalid embedding dimensions")
        return vectors

    @staticmethod
    def _is_transient(error: Exception) -> bool:
        status = getattr(error, "status_code", getattr(error, "code", None))
        return status in {408, 425, 429, 500, 502, 503, 504}
