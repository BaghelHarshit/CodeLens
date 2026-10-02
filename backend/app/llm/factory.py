"""Construct the configured provider-neutral LLM adapter."""

from ..config import Settings
from .fake import FakeLLM
from .gemini import GeminiLLM
from .protocol import LLMProvider


def create_llm_provider(settings: Settings) -> LLMProvider:
    """Build the configured LLM without exposing vendor details to workflows."""
    if settings.llm_provider == "fake":
        return FakeLLM()
    if settings.llm_provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required for the Gemini LLM provider")
        return GeminiLLM(
            api_key=settings.gemini_api_key,
            model=settings.gemini_chat_model,
            temperature=settings.llm_temperature,
            max_output_tokens=settings.llm_max_output_tokens,
            timeout=settings.llm_timeout,
            max_retries=settings.llm_max_retries,
            backoff=settings.llm_retry_backoff,
        )
    raise ValueError(f"unsupported LLM provider: {settings.llm_provider}")
