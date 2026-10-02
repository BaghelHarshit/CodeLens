"""Provider-neutral contracts for language model generation."""

from typing import Protocol


class LLMProviderError(RuntimeError):
    """Base error for safe language-model failures."""


class LLMConfigurationError(LLMProviderError):
    """Raised when the provider is configured incorrectly."""


class LLMGenerationError(LLMProviderError):
    """Raised when generation fails or returns malformed content."""


class LLMRefusalError(LLMProviderError):
    """Raised when the provider blocks or refuses a request."""


class LLMProvider(Protocol):
    """Minimal interface shared by Q&A and review workflows."""

    def invoke(self, prompt: str) -> str:
        """Generate a response for one prompt."""
        ...
