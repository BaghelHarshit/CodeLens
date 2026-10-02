"""Session registry seam for shared Q&A and review retrieval."""

from ..indexing import IndexingRegistry
from .models import RetrievalNotReadyError
from .service import RetrievalLimits, RetrievalService


def for_session(
    registry: IndexingRegistry,
    session_id: str,
    limits: RetrievalLimits | None = None,
) -> RetrievalService:
    """Return a retrieval service backed by the session's single indexed store."""
    index = registry.index(session_id)
    if index is None or not index.ready:
        raise RetrievalNotReadyError("repository retrieval is not ready")
    return RetrievalService(index, limits)
