"""HTTP contract tests for temporary sessions."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.session import SessionManager


def test_create_and_delete_session_api(tmp_path: Path) -> None:
    app.state.session_manager = SessionManager(tmp_path)
    client = TestClient(app)

    created = client.post("/api/session")

    assert created.status_code == 201
    payload = created.json()
    assert payload["status"] == "created"
    assert len(payload["session_id"]) == 48
    assert str(tmp_path) not in created.text

    deleted = client.delete(f"/api/session/{payload['session_id']}")

    assert deleted.status_code == 200
    assert deleted.json() == {"session_id": payload["session_id"], "status": "deleted"}
    assert not (tmp_path / payload["session_id"]).exists()


def test_delete_unknown_session_uses_safe_error(tmp_path: Path) -> None:
    app.state.session_manager = SessionManager(tmp_path)
    client = TestClient(app)

    response = client.delete("/api/session/../outside")

    assert response.status_code in {404, 307}

    response = client.delete("/api/session/not-a-session")
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "SESSION_NOT_FOUND", "message": "Session was not found."}
    }
    assert str(tmp_path) not in response.text
