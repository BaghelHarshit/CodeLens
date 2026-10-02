"""HTTP endpoint for secure local repository ingestion."""

from typing import cast

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import JSONResponse

from .config import Settings
from .repository import IngestionError, ingest_repository
from .session import SessionManager
from .session.models import InvalidSessionStateError, SessionNotFoundError, SessionState

router = APIRouter(prefix="/api/session", tags=["repository"])


def _manager(request: Request) -> SessionManager:
    return cast(SessionManager, request.app.state.session_manager)


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


@router.post("/{session_id}/repository", status_code=202)  # noqa: B008
async def upload_repository(
    request: Request,
    session_id: str,
    repository: UploadFile | None = File(default=None),  # noqa: B008
) -> dict[str, object]:
    """Accept and safely extract a ZIP repository for its first session upload."""

    if repository is None:
        raise IngestionError("MISSING_REPOSITORY", "The repository upload is required.")
    manager = _manager(request)
    session = manager.repository_session(session_id)
    manager.transition(session_id, SessionState.UPLOADING)
    try:
        result = await ingest_repository(repository, session, _settings(request))
    except Exception:
        if session.state is SessionState.UPLOADING:
            manager.transition(session_id, SessionState.FAILED)
        raise
    manager.transition(session_id, SessionState.INDEXING)
    return {
        "session_id": session_id,
        "status": "indexing",
        "message": "Repository accepted; indexing started",
        "files_accepted": result.files_accepted,
        "files_skipped": result.files_skipped,
        "extracted_bytes": result.extracted_bytes,
        "warnings": list(result.warnings),
    }


def repository_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """Convert ingestion and session errors into safe API errors."""

    if isinstance(exc, IngestionError):
        status_code = exc.status_code
        code = exc.code
        message = str(exc)
    elif isinstance(exc, SessionNotFoundError):
        status_code = 404
        code = "SESSION_NOT_FOUND"
        message = "Session was not found."
    elif isinstance(exc, InvalidSessionStateError):
        status_code = 409
        code = "INVALID_SESSION_STATE"
        message = str(exc)
    else:
        status_code = 500
        code = "INGESTION_FAILED"
        message = "The repository could not be accepted."
    return JSONResponse(
        status_code=status_code, content={"error": {"code": code, "message": message}}
    )


REPOSITORY_EXCEPTION_TYPES = (IngestionError, SessionNotFoundError, InvalidSessionStateError)
