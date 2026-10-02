"""Secure in-memory management of temporary session workspaces."""

from __future__ import annotations

import secrets
import shutil
import tempfile
from pathlib import Path
from threading import RLock

from .models import (
    ALLOWED_TRANSITIONS,
    InvalidSessionStateError,
    Session,
    SessionNotFoundError,
    SessionState,
    SessionStorageError,
)

_SESSION_ID_BYTES = 24
_SESSION_ID_LENGTH = _SESSION_ID_BYTES * 2


class SessionManager:
    """Create and manage isolated temporary workspaces for active sessions."""

    def __init__(self, temp_root: str | Path | None = None) -> None:
        configured_root = (
            Path(temp_root) if temp_root is not None else Path(tempfile.gettempdir()) / "codelens"
        )
        self._root = configured_root.expanduser().resolve()
        self._sessions: dict[str, Session] = {}
        self._lock = RLock()

    @property
    def temp_root(self) -> Path:
        """Return the resolved parent directory for session workspaces."""

        return self._root

    def create(self) -> Session:
        """Create a unique session and its three isolated workspace directories."""

        with self._lock:
            try:
                self._root.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise SessionStorageError("Unable to prepare temporary session storage.") from exc

            for _ in range(10):
                session_id = secrets.token_hex(_SESSION_ID_BYTES)
                session_root = self._root / session_id
                try:
                    session_root.mkdir()
                except FileExistsError:
                    continue
                except OSError as exc:
                    raise SessionStorageError("Unable to create a temporary session.") from exc

                try:
                    (session_root / "repo").mkdir()
                    (session_root / "index").mkdir()
                    (session_root / "metadata").mkdir()
                except OSError as exc:
                    shutil.rmtree(session_root, ignore_errors=True)
                    raise SessionStorageError(
                        "Unable to create a temporary session workspace."
                    ) from exc

                session = Session(session_id=session_id, root=session_root)
                self._sessions[session_id] = session
                return session

            raise SessionStorageError("Unable to allocate a unique temporary session.")

    def get(self, session_id: str) -> Session:
        """Return a registered active session after validating its identifier."""

        self._validate_session_id(session_id)
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionNotFoundError("Session was not found.")
            return session

    def repository_session(self, session_id: str) -> Session:
        """Return a session that can receive its first repository upload."""

        with self._lock:
            session = self.get(session_id)
            if session.state is not SessionState.CREATED:
                raise InvalidSessionStateError("Repository upload is not valid for this session.")
            return session

    def transition(self, session_id: str, state: SessionState) -> Session:
        """Move a session through an allowed lifecycle transition."""

        with self._lock:
            session = self.get(session_id)
            if state not in ALLOWED_TRANSITIONS[session.state]:
                raise InvalidSessionStateError(
                    f"Cannot transition from {session.state.value} to {state.value}."
                )
            session.state = state
            return session

    def delete(self, session_id: str) -> None:
        """Delete a session workspace safely and make repeated deletion harmless."""

        self._validate_session_id(session_id)
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionNotFoundError("Session was not found.")

            if session.state is SessionState.DELETED:
                return

            self._assert_session_root(session.root, session.session_id)
            try:
                shutil.rmtree(session.root, ignore_errors=False)
            except FileNotFoundError:
                pass
            except OSError as exc:
                raise SessionStorageError("Unable to remove the temporary session.") from exc

            session.state = SessionState.DELETED

    def _assert_session_root(self, session_root: Path, session_id: str) -> None:
        """Ensure cleanup can only target the expected direct child directory."""

        root = self._root.resolve()
        candidate = session_root.resolve(strict=False)
        expected = root / session_id
        if candidate != expected or candidate.parent != root:
            raise SessionStorageError("Temporary session storage boundary was violated.")
        if candidate == root or candidate.is_symlink():
            raise SessionStorageError("Temporary session storage boundary was violated.")

    @staticmethod
    def _validate_session_id(session_id: str) -> None:
        """Reject malformed IDs before registry or filesystem access."""

        if (
            not isinstance(session_id, str)
            or len(session_id) != _SESSION_ID_LENGTH
            or any(character not in "0123456789abcdef" for character in session_id)
        ):
            raise SessionNotFoundError("Session was not found.")
