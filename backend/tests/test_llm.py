from types import SimpleNamespace

import pytest

from app.config import Settings
from app.llm import (
    FakeLLM,
    GeminiLLM,
    LLMGenerationError,
    LLMRefusalError,
    create_llm_provider,
)


def test_fake_provider_is_deterministic_and_records_prompt() -> None:
    provider = FakeLLM("answer")

    assert provider.invoke("question") == "answer"
    assert provider.calls == ["question"]


def test_factory_defaults_to_offline_provider() -> None:
    provider = create_llm_provider(Settings())

    assert isinstance(provider, FakeLLM)


def test_factory_requires_key_for_live_provider() -> None:
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        create_llm_provider(Settings(llm_provider="gemini"))


def test_gemini_success_and_request_config() -> None:
    calls: list[dict[str, object]] = []

    class Client:
        class Models:
            def generate_content(self, **kwargs):
                calls.append(kwargs)
                return SimpleNamespace(text=" generated ", candidates=[])

        models = Models()

    result = GeminiLLM(
        api_key="secret",
        model="chat-model",
        temperature=0.4,
        max_output_tokens=100,
        client=Client(),
    ).invoke("prompt")

    assert result == "generated"
    assert calls == [
        {
            "model": "chat-model",
            "contents": "prompt",
            "config": {"temperature": 0.4, "max_output_tokens": 100},
        }
    ]


def test_gemini_retries_transient_failures() -> None:
    attempts = 0
    sleeps: list[float] = []

    class Error(Exception):
        status_code = 503

    class Client:
        class Models:
            def generate_content(self, **kwargs):
                nonlocal attempts
                attempts += 1
                if attempts < 3:
                    raise Error()
                return SimpleNamespace(text="ok", candidates=[])

        models = Models()

    provider = GeminiLLM(
        api_key="secret",
        model="model",
        max_retries=2,
        backoff=0.1,
        client=Client(),
        sleep=sleeps.append,
    )

    assert provider.invoke("prompt") == "ok"
    assert attempts == 3
    assert sleeps == [0.1, 0.2]


def test_gemini_rejects_malformed_and_refused_responses() -> None:
    class Client:
        class Models:
            def generate_content(self, **kwargs):
                return SimpleNamespace(text="", candidates=[])

        models = Models()

    with pytest.raises(LLMGenerationError):
        GeminiLLM(api_key="secret", model="model", client=Client()).invoke("prompt")

    class RefusedClient:
        class Models:
            def generate_content(self, **kwargs):
                return SimpleNamespace(
                    text="", prompt_feedback=SimpleNamespace(block_reason="SAFETY"), candidates=[]
                )

        models = Models()

    with pytest.raises(LLMRefusalError):
        GeminiLLM(api_key="secret", model="model", client=RefusedClient()).invoke("prompt")


def test_provider_errors_do_not_expose_prompt_or_key() -> None:
    provider = FakeLLM(error=RuntimeError("prompt secret"))

    with pytest.raises(LLMGenerationError) as error:
        provider.invoke("private prompt")

    assert "private prompt" not in str(error.value)
    assert "secret" not in str(error.value)
