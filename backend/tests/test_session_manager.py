"""Tests for temporary session isolation and lifecycle management."""

from pathlib import Path

import pytest

from app.session import (
    InvalidSessionStateError,
    SessionManager,
    SessionNotFoundError,
    SessionState,
)


def test_create_allocates_isolated_workspace(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path / "sessions")

    first = manager.create()
    second = manager.create()

    assert first.session_id != second.session_id
    assert first.root != second.root
    assert first.root.parent == manager.temp_root
    assert {path.name for path in first.root.iterdir()} == {"repo", "index", "metadata"}
    assert {path.name for path in second.root.iterdir()} == {"repo", "index", "metadata"}
    assert manager.get(first.session_id) is first


def test_lifecycle_transitions_are_guarded(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create()

    manager.transition(session.session_id, SessionState.UPLOADING)
    manager.transition(session.session_id, SessionState.INDEXING)
    manager.transition(session.session_id, SessionState.READY)

    with pytest.raises(InvalidSessionStateError):
        manager.transition(session.session_id, SessionState.FAILED)


def test_failed_upload_can_be_deleted(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create()
    manager.transition(session.session_id, SessionState.UPLOADING)
    manager.transition(session.session_id, SessionState.FAILED)

    manager.delete(session.session_id)

    assert session.state is SessionState.DELETED
    assert not session.root.exists()
    with pytest.raises(InvalidSessionStateError):
        manager.transition(session.session_id, SessionState.CREATED)


def test_delete_is_idempotent_and_cleans_contents(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create()
    (session.repository_dir / "source.py").write_text("print('fixture')", encoding="utf-8")
    (session.index_dir / "index.bin").write_bytes(b"index")
    (session.metadata_dir / "chunks.json").write_text("{}", encoding="utf-8")

    manager.delete(session.session_id)
    manager.delete(session.session_id)

    assert not session.root.exists()


def test_unknown_or_malformed_session_is_not_found(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)

    with pytest.raises(SessionNotFoundError):
        manager.get("../outside")
    with pytest.raises(SessionNotFoundError):
        manager.delete("not-a-session")
    with pytest.raises(SessionNotFoundError):
        manager.get("0" * 48)
