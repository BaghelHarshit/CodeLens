"""HTTP endpoint for bounded, grounded repository code review."""

from typing import cast

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .config import Settings
from .indexing import IndexingRegistry
from .llm import LLMProvider, create_llm_provider
from .review import ReviewWorkflowError, run_review_workflow
from .retrieval import RetrievalNotReadyError
from .session import SessionManager
from .session.models import SessionDeletedError, SessionNotFoundError

router = APIRouter(prefix="/api/session", tags=["review"])


class ReviewRequest(BaseModel):
    """Validated unified diff submitted for review."""

    diff: str = Field(min_length=1, max_length=200_000)


def _manager(request: Request) -> SessionManager:
    return cast(SessionManager, request.app.state.session_manager)


def _registry(request: Request) -> IndexingRegistry:
    return cast(IndexingRegistry, request.app.state.indexing_registry)


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def _llm(request: Request, settings: Settings) -> LLMProvider:
    provider = getattr(request.app.state, "llm_provider", None)
    if provider is None:
        provider = create_llm_provider(settings)
        request.app.state.llm_provider = provider
    return provider


@router.post("/{session_id}/review")
def review(request: Request, session_id: str, payload: ReviewRequest) -> dict[str, object]:
    """Review a unified diff using the session's shared repository index."""
    session = _manager(request).get(session_id)
    if session.state.value == "deleted":
        raise SessionDeletedError("Session has been deleted.")
    result = run_review_workflow(
        session_id=session_id,
        diff=payload.diff,
        registry=_registry(request),
        llm=_llm(request, _settings(request)),
    )
    return result.to_dict()


def review_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """Convert review failures into stable, non-sensitive API errors."""
    if isinstance(exc, SessionNotFoundError):
        status, code, message = 404, "SESSION_NOT_FOUND", "Session was not found."
    elif isinstance(exc, SessionDeletedError):
        status, code, message = 410, "SESSION_DELETED", "Session has been deleted."
    elif isinstance(exc, RetrievalNotReadyError) or (
        isinstance(exc, ReviewWorkflowError) and exc.code == "SESSION_NOT_READY"
    ):
        status, code, message = 409, "SESSION_NOT_READY", "The repository is not ready for review."
    elif isinstance(exc, ReviewWorkflowError):
        if exc.code == "INVALID_DIFF":
            status, code, message = 422, "INVALID_DIFF", "The review diff is invalid."
        elif exc.code in {"MALFORMED_LLM_OUTPUT", "LLM_FAILED"}:
            status, code, message = 502, exc.code, exc.message
        elif exc.code == "PROMPT_TOO_LARGE":
            status, code, message = 422, exc.code, "The review context exceeds the allowed limit."
        else:
            status, code, message = 500, "REVIEW_FAILED", "The review could not be completed."
    else:
        status, code, message = 500, "REVIEW_FAILED", "The review could not be completed."
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


REVIEW_EXCEPTION_TYPES = (
    SessionNotFoundError,
    SessionDeletedError,
    RetrievalNotReadyError,
    ReviewWorkflowError,
)
