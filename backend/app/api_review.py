"""HTTP endpoint for bounded, grounded repository code review."""

from typing import Literal, cast

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

from .config import Settings
from .indexing import IndexingRegistry
from .llm import LLMProvider, create_llm_provider
from .review import ReviewWorkflowError, run_review_workflow
from .review.git_source import GitSourceError, latest_commit_diff
from .retrieval import RetrievalNotReadyError
from .session import SessionManager
from .session.models import SessionDeletedError, SessionNotFoundError

router = APIRouter(prefix="/api/session", tags=["review"])


class ReviewRequest(BaseModel):
    """Validated review source request."""

    source: Literal["manual", "last_commit"] = "manual"
    diff: str | None = Field(default=None, min_length=1, max_length=200_000)

    @model_validator(mode="before")
    @classmethod
    def default_legacy_source(cls, values: object) -> object:
        if isinstance(values, dict) and "source" not in values:
            return {**values, "source": "manual"}
        return values

    @model_validator(mode="after")
    def validate_source(self) -> "ReviewRequest":
        if self.source == "manual" and self.diff is None:
            raise ValueError("manual review requires a diff")
        if self.source == "last_commit" and self.diff is not None:
            raise ValueError("last-commit review does not accept a diff")
        return self


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
    diff = payload.diff
    if payload.source == "last_commit":
        diff = latest_commit_diff(session.repository_dir)
    assert diff is not None
    result = run_review_workflow(
        session_id=session_id,
        diff=diff,
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
    elif isinstance(exc, GitSourceError):
        git_statuses = {
            "GIT_METADATA_MISSING": (422, "GIT_METADATA_MISSING", "The uploaded repository does not contain Git metadata."),
            "GIT_REPOSITORY_UNAVAILABLE": (422, "GIT_REPOSITORY_UNAVAILABLE", "The repository is unavailable for last-commit review."),
            "EMPTY_LAST_COMMIT": (422, "EMPTY_LAST_COMMIT", "The latest Git commit contains no changes."),
            "MALFORMED_LAST_COMMIT": (422, "MALFORMED_LAST_COMMIT", "The latest Git commit diff is invalid."),
            "GIT_DIFF_TOO_LARGE": (422, "GIT_DIFF_TOO_LARGE", "The latest Git commit diff is too large."),
            "GIT_TIMEOUT": (502, "GIT_COMMAND_FAILED", "Git could not read the repository."),
        }
        status, code, message = git_statuses.get(
            exc.code, (422, "GIT_COMMAND_FAILED", "Git could not read the repository.")
        )
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
    GitSourceError,
)
