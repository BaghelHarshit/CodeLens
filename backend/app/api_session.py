"""HTTP endpoints for temporary CodeLens sessions."""

from typing import cast

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .session import SessionManager
from .session.models import SessionNotFoundError, SessionStorageError

router = APIRouter(prefix="/api/session", tags=["sessions"])


def get_session_manager(request: Request) -> SessionManager:
    """Return the application-scoped session manager."""

    return cast(SessionManager, request.app.state.session_manager)


def _session_response(session_id: str, status: str) -> dict[str, str]:
    return {"session_id": session_id, "status": status}


@router.post("", status_code=201)
def create_session(request: Request) -> dict[str, str]:
    """Create a temporary repository-analysis session."""

    session = get_session_manager(request).create()
    return _session_response(session.session_id, session.state.value)


@router.delete("/{session_id}")
def delete_session(request: Request, session_id: str) -> dict[str, str]:
    """Delete a session and its temporary workspace."""

    get_session_manager(request).delete(session_id)
    return _session_response(session_id, "deleted")


def session_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """Convert internal session errors into the documented safe error shape."""

    if isinstance(exc, SessionNotFoundError):
        status_code = 404
        code = "SESSION_NOT_FOUND"
    else:
        status_code = 500
        code = "SESSION_STORAGE_ERROR"
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": str(exc)}},
    )


SESSION_EXCEPTION_TYPES = (SessionNotFoundError, SessionStorageError)
