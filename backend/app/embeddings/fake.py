"""Deterministic embedding provider for offline development and tests."""

from collections.abc import Sequence
from hashlib import sha256

from .protocol import EmbeddingProviderError, Vector


class FakeEmbeddings:
    """Create stable vectors without contacting a provider."""

    def __init__(self, dimensions: int = 8) -> None:
        if dimensions < 1:
            raise ValueError("dimensions must be positive")
        self.dimensions = dimensions

    def embed_query(self, text: str) -> Vector:
        """Return a deterministic vector for one query."""
        return self._embed(text)

    def embed_documents(self, texts: Sequence[str]) -> list[Vector]:
        """Return deterministic vectors for a batch of documents."""
        if not texts:
            raise EmbeddingProviderError("at least one text is required")
        return [self._embed(text) for text in texts]

    def _embed(self, text: str) -> Vector:
        digest = sha256(text.encode("utf-8")).digest()
        repeated = (digest * ((self.dimensions + 31) // 32))[: self.dimensions]
        return [byte / 255.0 for byte in repeated]
