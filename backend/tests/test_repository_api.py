"""HTTP tests for repository uploads."""

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient

from app.main import app
from app.session import SessionManager


def _archive() -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("src/greeting.py", "def greet():\n    return 'hello'\n")
    return output.getvalue()


def test_repository_upload_starts_indexing(tmp_path: Path) -> None:
    app.state.session_manager = SessionManager(tmp_path)
    client = TestClient(app)
    session_id = client.post("/api/session").json()["session_id"]

    response = client.post(
        f"/api/session/{session_id}/repository",
        files={"repository": ("repo.zip", _archive(), "application/zip")},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "indexing"
    assert response.json()["files_accepted"] == 1
    assert str(tmp_path) not in response.text


def test_repository_upload_requires_file(tmp_path: Path) -> None:
    app.state.session_manager = SessionManager(tmp_path)
    client = TestClient(app)
    session_id = client.post("/api/session").json()["session_id"]

    response = client.post(f"/api/session/{session_id}/repository")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MISSING_REPOSITORY"
