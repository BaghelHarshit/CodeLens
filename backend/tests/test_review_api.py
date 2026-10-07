import json

from fastapi.testclient import TestClient

from app.chunking.models import CodeChunk
from app.indexing import IndexingRegistry, SearchResult
from app.llm.fake import FakeLLM
from app.main import app
from app.session import SessionManager

DIFF = """diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -1,1 +1,2 @@
 def run():
+    return False
"""


def setup_ready(tmp_path, response: str = '{"findings":[]}'):
    manager = SessionManager(tmp_path)
    session = manager.create()
    chunk = CodeChunk(
        chunk_id="related",
        relative_path="tests/test_app.py",
        symbol_name="test_run",
        symbol_type="function",
        language="python",
        source="assert run()",
        start_line=1,
        end_line=1,
        parent_start_line=1,
        parent_end_line=1,
    )

    class Index:
        ready = True

        def search(self, query: str, top_k: int) -> list[SearchResult]:
            return [SearchResult(0.9, chunk)]

    registry = IndexingRegistry()
    registry._indexes[session.session_id] = Index()  # type: ignore[assignment]
    llm = FakeLLM(response)
    app.state.session_manager = manager
    app.state.indexing_registry = registry
    app.state.llm_provider = llm
    return session, llm


def test_review_endpoint_returns_findings_and_no_findings(tmp_path) -> None:
    finding = json.dumps(
        {
            "findings": [
                {
                    "severity": "low",
                    "file": "src/app.py",
                    "line": 2,
                    "issue": "Boolean result is ambiguous.",
                    "explanation": "The changed line returns a literal false value.",
                }
            ]
        }
    )
    session, _ = setup_ready(tmp_path, finding)
    response = TestClient(app).post(
        f"/api/session/{session.session_id}/review", json={"diff": DIFF}
    )
    assert response.status_code == 200
    assert response.json()["findings"][0]["file"] == "src/app.py"

    session, _ = setup_ready(tmp_path / "second")
    response = TestClient(app).post(
        f"/api/session/{session.session_id}/review", json={"diff": DIFF}
    )
    assert response.status_code == 200
    assert response.json() == {"outcome": "no_findings", "findings": []}


def test_review_endpoint_maps_input_lifecycle_and_provider_errors(tmp_path) -> None:
    manager = SessionManager(tmp_path)
    app.state.session_manager = manager
    app.state.indexing_registry = IndexingRegistry()
    client = TestClient(app)

    missing = client.post("/api/session/not-a-session/review", json={"diff": DIFF})
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "SESSION_NOT_FOUND"

    session = manager.create()
    not_ready = client.post(f"/api/session/{session.session_id}/review", json={"diff": DIFF})
    assert not_ready.status_code == 409
    assert not_ready.json()["error"]["code"] == "SESSION_NOT_READY"

    invalid = client.post(f"/api/session/{session.session_id}/review", json={"diff": " "})
    assert invalid.status_code == 422

    too_long = client.post(f"/api/session/{session.session_id}/review", json={"diff": "x" * 200001})
    assert too_long.status_code == 422


def test_review_endpoint_handles_insufficient_context_without_llm(tmp_path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create()

    class EmptyIndex:
        ready = True

        def search(self, query: str, top_k: int) -> list[SearchResult]:
            return []

    registry = IndexingRegistry()
    registry._indexes[session.session_id] = EmptyIndex()  # type: ignore[assignment]
    llm = FakeLLM()
    app.state.session_manager = manager
    app.state.indexing_registry = registry
    app.state.llm_provider = llm

    response = TestClient(app).post(
        f"/api/session/{session.session_id}/review", json={"diff": DIFF}
    )
    assert response.status_code == 200
    assert response.json()["outcome"] == "insufficient_context"
    assert llm.calls == []


def test_review_endpoint_maps_malformed_and_provider_failures(tmp_path) -> None:
    session, _ = setup_ready(tmp_path, "not json")
    response = TestClient(app).post(
        f"/api/session/{session.session_id}/review", json={"diff": DIFF}
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "MALFORMED_LLM_OUTPUT"

    session, _ = setup_ready(tmp_path / "failure")
    from app.llm.fake import FakeLLM

    app.state.llm_provider = FakeLLM(error=RuntimeError("private prompt"))
    response = TestClient(app).post(
        f"/api/session/{session.session_id}/review", json={"diff": DIFF}
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "LLM_FAILED"
    assert "private prompt" not in response.text
