import json

import pytest

from app.chunking.models import CodeChunk
from app.embeddings.fake import FakeEmbeddings
from app.indexing import IndexValidationError, SessionIndex
from app.session.manager import SessionManager


def chunk(path: str, source: str, line: int) -> CodeChunk:
    return CodeChunk(
        chunk_id=f"{path}-{line}",
        relative_path=path,
        symbol_name="run",
        symbol_type="function",
        language="python",
        source=source,
        start_line=line,
        end_line=line,
        parent_start_line=line,
        parent_end_line=line,
    )


def test_build_search_and_reload(tmp_path) -> None:
    provider = FakeEmbeddings(4)
    index = SessionIndex(tmp_path, provider)
    chunks = [chunk("src/a.py", "alpha", 1), chunk("src/b.py", "beta", 3)]
    index.build(chunks)
    assert index.ready and index.count == 2
    results = index.search("alpha", 1)
    assert len(results) == 1
    assert results[0].chunk.relative_path == "src/a.py"
    reloaded = SessionIndex(tmp_path, provider)
    reloaded.load()
    assert reloaded.search("beta", 1)[0].chunk.relative_path == "src/b.py"


def test_rejects_empty_and_invalid_vectors(tmp_path) -> None:
    index = SessionIndex(tmp_path, FakeEmbeddings(4))
    with pytest.raises(IndexValidationError):
        index.build([])


def test_metadata_tampering_is_rejected(tmp_path) -> None:
    index = SessionIndex(tmp_path, FakeEmbeddings(4))
    index.build([chunk("src/a.py", "alpha", 1)])
    metadata = tmp_path / "metadata.json"
    payload = json.loads(metadata.read_text())
    payload["dimensions"] = 99
    metadata.write_text(json.dumps(payload))
    with pytest.raises(IndexValidationError):
        SessionIndex(tmp_path, FakeEmbeddings(4)).load()


def test_session_delete_removes_index_artifacts(tmp_path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create()
    SessionIndex(session.index_dir, FakeEmbeddings(4)).build([chunk("a.py", "alpha", 1)])
    assert (session.index_dir / "vectors.faiss").exists()
    manager.delete(session.session_id)
    assert not session.root.exists()
