"""HTTP status endpoint for repository indexing."""

from typing import cast

from fastapi import APIRouter, Request

from .indexing import IndexingRegistry
from .session import SessionManager
from .session.models import SessionNotFoundError

router = APIRouter(prefix="/api/session", tags=["indexing"])


def _registry(request: Request) -> IndexingRegistry:
    return cast(IndexingRegistry, request.app.state.indexing_registry)


@router.get("/{session_id}/status")
def indexing_status(request: Request, session_id: str) -> dict[str, object]:
    """Return bounded indexing progress and readiness information."""
    manager = cast(SessionManager, request.app.state.session_manager)
    manager.get(session_id)
    status = _registry(request).status(session_id)
    if status is None:
        raise SessionNotFoundError("Indexing status was not found.")
    return status.to_dict()
