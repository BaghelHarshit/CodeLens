"""Provider-neutral embedding services."""

from .factory import create_embedding_provider
from .fake import FakeEmbeddings
from .protocol import EmbeddingProvider, EmbeddingProviderError

__all__ = [
    "EmbeddingProvider",
    "EmbeddingProviderError",
    "FakeEmbeddings",
    "create_embedding_provider",
]
