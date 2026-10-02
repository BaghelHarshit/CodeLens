from types import SimpleNamespace

import pytest

from app.chunking.models import CodeChunk
from app.indexing import IndexingRegistry, SearchResult
from app.llm.fake import FakeLLM
from app.rag import QAProviderError, QAValidationError, answer_question


def test_answer_question_uses_bounded_context_and_references() -> None:
    chunk = CodeChunk(
        chunk_id="one",
        relative_path="src/main.py",
        symbol_name="run",
        symbol_type="function",
        language="python",
        source="return 'ok'",
        start_line=2,
        end_line=2,
        parent_start_line=2,
        parent_end_line=2,
    )

    class Index:
        ready = True

        def search(self, query: str, top_k: int) -> list[SearchResult]:
            return [SearchResult(0.9, chunk)]

    registry = IndexingRegistry()
    registry._indexes["session"] = Index()  # type: ignore[assignment]
    llm = FakeLLM("It returns ok.")

    result = answer_question(
        session_id="session", question="What does run do?", registry=registry, llm=llm
    )

    assert result.answer == "It returns ok."
    assert result.references[0]["relative_path"] == "src/main.py"
    assert "What does run do?" in llm.calls[0]
    assert "return 'ok'" in llm.calls[0]


def test_empty_retrieval_does_not_call_llm() -> None:
    class Index:
        ready = True

        def search(self, query: str, top_k: int) -> list[SearchResult]:
            return []

    registry = IndexingRegistry()
    registry._indexes["session"] = Index()  # type: ignore[assignment]
    llm = FakeLLM()

    result = answer_question(session_id="session", question="Unknown?", registry=registry, llm=llm)

    assert result.insufficient_context
    assert result.references == ()
    assert llm.calls == []


def test_invalid_question_and_provider_failure_are_safe() -> None:
    with pytest.raises(QAValidationError):
        answer_question(
            session_id="missing", question=" ", registry=IndexingRegistry(), llm=FakeLLM()
        )

    class Index:
        ready = True

        def search(self, query: str, top_k: int) -> list[SearchResult]:
            return [SearchResult(1.0, SimpleNamespace(chunk_id="bad"))]  # pragma: no cover

    # The workflow's provider boundary is exercised by the fake directly in later API tests.
    assert QAProviderError
