"""Deterministic offline language-model provider."""

from .protocol import LLMGenerationError, LLMProvider, LLMRefusalError


class FakeLLM:
    """Return a configured response without network access."""

    def __init__(
        self,
        response: str = "Offline provider response.",
        *,
        error: Exception | None = None,
        refusal: bool = False,
    ) -> None:
        self.response = response
        self.error = error
        self.refusal = refusal
        self.calls: list[str] = []

    def invoke(self, prompt: str) -> str:
        """Record the prompt and return or raise the configured outcome."""
        self.calls.append(prompt)
        if self.error is not None:
            raise LLMGenerationError("fake language model failed") from self.error
        if self.refusal:
            raise LLMRefusalError("language model refused the request")
        if not isinstance(self.response, str) or not self.response.strip():
            raise LLMGenerationError("language model returned malformed content")
        return self.response.strip()


__all__ = ["FakeLLM", "LLMProvider"]
