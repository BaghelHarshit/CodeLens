from app.config import Settings
from app.indexing import IndexingRegistry
from app.session.manager import SessionManager
from app.session.models import SessionState


def test_indexing_pipeline_reaches_ready(tmp_path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create()
    (session.repository_dir / "main.py").write_text("def hello():\n    return 'ok'\n")
    registry = IndexingRegistry()
    manager.transition(session.session_id, session.state.UPLOADING)
    manager.transition(session.session_id, session.state.INDEXING)
    registry.start(session, Settings(temp_root=str(tmp_path)))
    status = registry.status(session.session_id)
    assert status is not None
    assert status.state == "ready"
    assert status.chunks_indexed == 1
    assert session.state.value == "ready"


def test_indexing_failure_is_terminal_and_safe(tmp_path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create()
    manager.transition(session.session_id, session.state.UPLOADING)
    manager.transition(session.session_id, session.state.INDEXING)
    registry = IndexingRegistry()
    registry.start(session, Settings(temp_root=str(tmp_path)))
    status = registry.status(session.session_id)
    assert status is not None
    assert status.state == "failed"
    assert status.error_code == "INDEXING_FAILED"
    assert status.error_message == "The repository could not be indexed."


def test_deleted_session_cannot_publish_index_status(tmp_path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create()
    manager.transition(session.session_id, SessionState.UPLOADING)
    manager.transition(session.session_id, SessionState.INDEXING)
    registry = IndexingRegistry()
    manager.delete(session.session_id)
    registry.start(session, Settings(temp_root=str(tmp_path)))
    assert registry.status(session.session_id) is None
    assert not session.root.exists()
