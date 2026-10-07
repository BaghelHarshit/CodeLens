from fastapi.testclient import TestClient

from app.chunking.models import CodeChunk
from app.indexing import IndexingRegistry, SearchResult
from app.llm.fake import FakeLLM
from app.main import app
from app.session import SessionManager


def _ready_index(chunk: CodeChunk):
    class Index:
        ready = True

        def search(self, query: str, top_k: int) -> list[SearchResult]:
            return [SearchResult(0.9, chunk)]

    return Index()


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


def test_chat_enforces_question_limit_and_missing_session(tmp_path) -> None:
    manager = SessionManager(tmp_path)
    app.state.session_manager = manager
    app.state.indexing_registry = IndexingRegistry()
    client = TestClient(app)

    missing = client.post("/api/session/not-a-session/chat", json={"question": "hello"})
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "SESSION_NOT_FOUND"

    session = manager.create()
    too_long = client.post(f"/api/session/{session.session_id}/chat", json={"question": "x" * 4001})
    assert too_long.status_code == 422


def test_chat_maps_provider_failures_to_stable_error(tmp_path) -> None:
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
    registry = IndexingRegistry()
    registry._indexes[session.session_id] = _ready_index(chunk)  # type: ignore[assignment]
    app.state.session_manager = manager
    app.state.indexing_registry = registry
    app.state.llm_provider = FakeLLM(error=RuntimeError("offline failure"))

    response = TestClient(app).post(
        f"/api/session/{session.session_id}/chat", json={"question": "What does run do?"}
    )

    assert response.status_code == 502
    assert response.json() == {
        "error": {
            "code": "LLM_FAILED",
            "message": "The language model could not answer the question.",
        }
    }


def test_chat_rejects_deleted_session(tmp_path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create()
    manager.delete(session.session_id)
    app.state.session_manager = manager
    app.state.indexing_registry = IndexingRegistry()

    response = TestClient(app).post(
        f"/api/session/{session.session_id}/chat", json={"question": "hello"}
    )

    assert response.status_code == 410
    assert response.json()["error"]["code"] == "SESSION_DELETED"
