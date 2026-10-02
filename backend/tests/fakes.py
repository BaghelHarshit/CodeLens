"""Deterministic provider doubles for offline tests."""

from hashlib import sha256


class FakeEmbeddings:
    """Create stable vectors without contacting an embedding provider."""

    def __init__(self, dimensions: int = 8) -> None:
        if dimensions < 1:
            raise ValueError("dimensions must be positive")
        self.dimensions = dimensions

    def embed_query(self, text: str) -> list[float]:
        """Return a deterministic vector for one query."""

        return self._embed(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return deterministic vectors for a batch of documents."""

        return [self._embed(text) for text in texts]

    def _embed(self, text: str) -> list[float]:
        digest = sha256(text.encode("utf-8")).digest()
        return [byte / 255.0 for byte in digest[: self.dimensions]]


class FakeLLM:
    """Return a predictable response without requiring an API key."""

    def __init__(self, response: str = "Offline provider response.") -> None:
        self.response = response
        self.calls: list[str] = []

    def invoke(self, prompt: str) -> str:
        """Record the prompt and return the configured response."""

        self.calls.append(prompt)
        return self.response
