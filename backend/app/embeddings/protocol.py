"""Contracts shared by embedding providers."""

from collections.abc import Sequence
from typing import Protocol, TypeAlias

Vector: TypeAlias = list[float]


class EmbeddingProviderError(RuntimeError):
    """Raised when a provider cannot return valid embeddings."""


class EmbeddingProvider(Protocol):
    """Minimal interface consumed by indexing and retrieval workflows."""

    dimensions: int

    def embed_query(self, text: str) -> Vector:
        """Embed one query."""
        ...

    def embed_documents(self, texts: Sequence[str]) -> list[Vector]:
        """Embed documents, preserving input order."""
        ...
