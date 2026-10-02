from fastapi.testclient import TestClient

from app.chunking.models import CodeChunk
from app.indexing import IndexingRegistry, SearchResult
from app.llm.fake import FakeLLM
from app.main import app
from app.session import SessionManager


def test_chat_returns_grounded_answer_and_references(tmp_path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create()
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
    registry._indexes[session.session_id] = Index()  # type: ignore[assignment]
    app.state.session_manager = manager
    app.state.indexing_registry = registry
    app.state.llm_provider = FakeLLM("The function returns ok.")

    response = TestClient(app).post(
        f"/api/session/{session.session_id}/chat", json={"question": "What does run do?"}
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "The function returns ok."
    assert response.json()["references"][0]["relative_path"] == "src/main.py"


def test_chat_rejects_not_ready_and_invalid_questions(tmp_path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create()
    app.state.session_manager = manager
    app.state.indexing_registry = IndexingRegistry()

    client = TestClient(app)
    response = client.post(f"/api/session/{session.session_id}/chat", json={"question": "hello"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SESSION_NOT_READY"

    response = client.post(f"/api/session/{session.session_id}/chat", json={"question": " "})
    assert response.status_code == 422
