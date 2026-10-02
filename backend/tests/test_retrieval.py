import pytest

from app.chunking.models import CodeChunk
from app.embeddings.fake import FakeEmbeddings
from app.indexing import SearchResult, SessionIndex
from app.retrieval import (
    RetrievalLimits,
    RetrievalNotReadyError,
    RetrievalService,
    RetrievalValidationError,
    for_session,
)
from app.session.manager import SessionManager


def make_chunk(chunk_id: str, source: str, path: str = "src/app.py") -> CodeChunk:
    return CodeChunk(
        chunk_id=chunk_id,
        relative_path=path,
        symbol_name="run",
        symbol_type="function",
        language="python",
        source=source,
        start_line=2,
        end_line=3,
        parent_start_line=2,
        parent_end_line=3,
    )


def test_retrieval_is_bounded_and_returns_safe_references(tmp_path) -> None:
    index = SessionIndex(tmp_path, FakeEmbeddings(4))
    index.build([make_chunk("one", "alpha"), make_chunk("two", "beta", "lib/util.py")])
    service = RetrievalService(
        index,
        RetrievalLimits(default_top_k=2, max_top_k=2, max_context_chars=150, max_chunk_chars=20),
    )

    result = service.retrieve(" alpha ")

    assert result.query == "alpha"
    assert len(result.references) <= 2
    assert all(
        not reference.relative_path.startswith(("/", "\\")) for reference in result.references
    )
    assert all("tmp" not in reference.relative_path for reference in result.references)
    assert len(result.context) <= 150
    assert all(reference.start_line == 2 for reference in result.references)


def test_retrieval_deduplicates_stable_chunk_ids(tmp_path) -> None:
    class DuplicateIndex:
        ready = True

        def search(self, query: str, top_k: int) -> list[SearchResult]:
            chunk = make_chunk("same", "source")
            return [SearchResult(0.9, chunk), SearchResult(0.8, chunk)]

    result = RetrievalService(DuplicateIndex()).retrieve("query")

    assert len(result.references) == 1
    assert result.references[0].score == 0.9


def test_retrieval_rejects_invalid_queries_and_limits(tmp_path) -> None:
    index = SessionIndex(tmp_path, FakeEmbeddings(4))
    index.build([make_chunk("one", "alpha")])
    service = RetrievalService(
        index, RetrievalLimits(default_top_k=2, max_query_chars=4, max_top_k=2)
    )

    with pytest.raises(RetrievalValidationError):
        service.retrieve("   ")
    with pytest.raises(RetrievalValidationError):
        service.retrieve("longer")
    with pytest.raises(RetrievalValidationError):
        service.retrieve("ok", 0)
    with pytest.raises(RetrievalValidationError):
        service.retrieve("ok", 3)


def test_unready_index_is_rejected(tmp_path) -> None:
    service = RetrievalService(SessionIndex(tmp_path, FakeEmbeddings(4)))

    with pytest.raises(RetrievalNotReadyError):
        service.retrieve("query")


def test_registry_returns_same_session_index_for_shared_workflows(tmp_path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create()
    (session.repository_dir / "main.py").write_text("def run():\n    return 'ok'\n")
    from app.config import Settings
    from app.indexing import IndexingRegistry
    from app.session.models import SessionState

    registry = IndexingRegistry()
    manager.transition(session.session_id, SessionState.UPLOADING)
    manager.transition(session.session_id, SessionState.INDEXING)
    registry.start(session, Settings(temp_root=str(tmp_path)))

    qa = for_session(registry, session.session_id)
    review = for_session(registry, session.session_id)

    assert qa.index is review.index is registry.index(session.session_id)
