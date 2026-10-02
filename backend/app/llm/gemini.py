"""Google Gemini language-model adapter."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from .protocol import LLMGenerationError, LLMRefusalError


class GeminiLLM:
    """Generate text with bounded retries and safe public errors."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        temperature: float = 0.2,
        max_output_tokens: int = 2048,
        timeout: float = 60.0,
        max_retries: int = 2,
        backoff: float = 0.25,
        client: Any | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if (
            not api_key
            or not model.strip()
            or temperature < 0
            or max_output_tokens < 1
            or timeout <= 0
            or max_retries < 0
            or backoff < 0
        ):
            raise ValueError("invalid Gemini language-model configuration")
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
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
            raise LLMGenerationError("Gemini provider dependency is not installed") from error
        return genai.Client(api_key=api_key)

    def invoke(self, prompt: str) -> str:
        """Generate one response without exposing provider details."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise LLMGenerationError("language-model prompt is invalid")
        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config={
                        "temperature": self.temperature,
                        "max_output_tokens": self.max_output_tokens,
                    },
                )
                return self._parse_response(response)
            except (LLMGenerationError, LLMRefusalError):
                raise
            except Exception as error:
                if attempt >= self.max_retries or not self._is_transient(error):
                    raise LLMGenerationError("Gemini language-model request failed") from error
                self._sleep(min(self.backoff * (2**attempt), 4.0))
        raise AssertionError("retry loop must return or raise")

    @staticmethod
    def _parse_response(response: Any) -> str:
        prompt_feedback = getattr(response, "prompt_feedback", None)
        if getattr(prompt_feedback, "block_reason", None):
            raise LLMRefusalError("language model refused the request")
        candidates = getattr(response, "candidates", None)
        if candidates and getattr(candidates[0], "finish_reason", None) in {
            "SAFETY",
            "BLOCKLIST",
            "PROHIBITED_CONTENT",
        }:
            raise LLMRefusalError("language model refused the request")
        text = getattr(response, "text", None)
        if not isinstance(text, str) or not text.strip():
            raise LLMGenerationError("language model returned malformed content")
        return text.strip()

    @staticmethod
    def _is_transient(error: Exception) -> bool:
        status = getattr(error, "status_code", getattr(error, "code", None))
        return status in {408, 425, 429, 500, 502, 503, 504}
