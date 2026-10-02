"""Deterministic provider doubles for offline tests."""

from app.embeddings.fake import FakeEmbeddings

__all__ = ["FakeEmbeddings", "FakeLLM"]


class FakeLLM:
    """Return a predictable response without requiring an API key."""

    def __init__(self, response: str = "Offline provider response.") -> None:
        self.response = response
        self.calls: list[str] = []

    def invoke(self, prompt: str) -> str:
        """Record the prompt and return the configured response."""

        self.calls.append(prompt)
        return self.response
