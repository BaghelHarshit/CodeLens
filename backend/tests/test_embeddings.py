from types import SimpleNamespace

import pytest

from app.config import Settings
from app.embeddings import FakeEmbeddings, create_embedding_provider
from app.embeddings.gemini import GeminiEmbeddings
from app.embeddings.protocol import EmbeddingProviderError


def test_fake_provider_is_deterministic_for_large_dimensions() -> None:
    provider = FakeEmbeddings(dimensions=40)
    assert provider.embed_query("same") == provider.embed_query("same")
    assert len(provider.embed_query("same")) == 40


def test_factory_selects_fake_provider() -> None:
    provider = create_embedding_provider(
        Settings(embedding_provider="fake", embedding_dimensions=4)
    )
    assert isinstance(provider, FakeEmbeddings)


def test_gemini_batches_and_preserves_order() -> None:
    calls: list[list[str]] = []

    class Client:
        class models:
            @staticmethod
            def embed_content(*, model: str, contents: list[str], config: dict[str, int]) -> object:
                calls.append(contents)
                return SimpleNamespace(
                    embeddings=[
                        SimpleNamespace(values=[float(len(text)), 1.0]) for text in contents
                    ]
                )

    provider = GeminiEmbeddings(
        api_key="secret",
        model="model",
        dimensions=2,
        batch_size=2,
        client=Client(),
    )
    assert provider.embed_documents(["a", "bb", "ccc"]) == [[1.0, 1.0], [2.0, 1.0], [3.0, 1.0]]
    assert calls == [["a", "bb"], ["ccc"]]


def test_gemini_retries_transient_failures() -> None:
    attempts = 0

    class TransientError(Exception):
        status_code = 503

    class Client:
        class models:
            @staticmethod
            def embed_content(**_: object) -> object:
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise TransientError()
                return SimpleNamespace(embeddings=[SimpleNamespace(values=[1.0, 2.0])])

    provider = GeminiEmbeddings(
        api_key="secret",
        model="model",
        dimensions=2,
        max_retries=1,
        sleep=lambda _: None,
        client=Client(),
    )
    assert provider.embed_query("source") == [1.0, 2.0]
    assert attempts == 2


def test_gemini_rejects_malformed_response() -> None:
    class Client:
        class models:
            @staticmethod
            def embed_content(**_: object) -> object:
                return SimpleNamespace(embeddings=[SimpleNamespace(values=[1.0])])

    provider = GeminiEmbeddings(api_key="secret", model="model", dimensions=2, client=Client())
    with pytest.raises(EmbeddingProviderError, match="invalid embedding"):
        provider.embed_query("source")


def test_gemini_requires_key() -> None:
    with pytest.raises(ValueError, match="API key"):
        GeminiEmbeddings(api_key="", model="model", dimensions=2)
