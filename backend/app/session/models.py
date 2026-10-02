"""Domain types for temporary CodeLens sessions."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class SessionState(Enum):
    """States in the repository session lifecycle."""

    CREATED = "created"
    UPLOADING = "uploading"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class SessionError(Exception):
    """Base class for safe session-management errors."""


class SessionNotFoundError(SessionError):
    """Raised when a session ID is not registered."""


class InvalidSessionStateError(SessionError):
    """Raised when an operation is invalid for the current session state."""


class SessionStorageError(SessionError):
    """Raised when a workspace cannot be safely created or removed."""


@dataclass(slots=True)
class Session:
    """In-memory session record with an isolated workspace."""

    session_id: str
    root: Path
    state: SessionState = SessionState.CREATED

    @property
    def repository_dir(self) -> Path:
        """Return the temporary repository directory."""

        return self.root / "repo"

    @property
    def index_dir(self) -> Path:
        """Return the temporary vector-index directory."""

        return self.root / "index"

    @property
    def metadata_dir(self) -> Path:
        """Return the temporary metadata directory."""

        return self.root / "metadata"


ALLOWED_TRANSITIONS: dict[SessionState, frozenset[SessionState]] = {
    SessionState.CREATED: frozenset({SessionState.UPLOADING, SessionState.DELETED}),
    SessionState.UPLOADING: frozenset(
        {SessionState.INDEXING, SessionState.FAILED, SessionState.DELETED}
    ),
    SessionState.INDEXING: frozenset(
        {SessionState.READY, SessionState.FAILED, SessionState.DELETED}
    ),
    SessionState.READY: frozenset({SessionState.DELETED}),
    SessionState.FAILED: frozenset({SessionState.DELETED}),
    SessionState.DELETED: frozenset(),
}
