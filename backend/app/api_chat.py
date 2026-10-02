"""HTTP endpoint for grounded repository questions."""

from typing import cast

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .config import Settings
from .indexing import IndexingRegistry
from .llm import create_llm_provider
from .rag import QAProviderError, QAValidationError, answer_question
from .retrieval import RetrievalNotReadyError, RetrievalValidationError
from .session import SessionManager
from .session.models import SessionNotFoundError

router = APIRouter(prefix="/api/session", tags=["chat"])


class ChatRequest(BaseModel):
    """Validated repository question."""

    question: str = Field(min_length=1, max_length=4000)


def _manager(request: Request) -> SessionManager:
    return cast(SessionManager, request.app.state.session_manager)


def _registry(request: Request) -> IndexingRegistry:
    return cast(IndexingRegistry, request.app.state.indexing_registry)


def _llm(request: Request, settings: Settings):
    provider = getattr(request.app.state, "llm_provider", None)
    if provider is None:
        provider = create_llm_provider(settings)
        request.app.state.llm_provider = provider
    return provider


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


@router.post("/{session_id}/chat")
def chat(request: Request, session_id: str, payload: ChatRequest) -> dict[str, object]:
    """Answer one question using only bounded indexed repository context."""
    _manager(request).get(session_id)
    result = answer_question(
        session_id=session_id,
        question=payload.question,
        registry=_registry(request),
        llm=_llm(request, _settings(request)),
    )
    return result.to_dict()


def chat_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """Convert Q&A failures into stable, safe API errors."""
    if isinstance(exc, SessionNotFoundError):
        status_code, code, message = 404, "SESSION_NOT_FOUND", "Session was not found."
    elif isinstance(exc, (RetrievalNotReadyError,)):
        status_code, code, message = (
            409,
            "SESSION_NOT_READY",
            "The repository is not ready for questions.",
        )
    elif isinstance(exc, (QAValidationError, RetrievalValidationError)):
        status_code, code, message = 422, "INVALID_QUESTION", str(exc)
    elif isinstance(exc, QAProviderError):
        status_code, code, message = 502, "LLM_FAILED", str(exc)
    else:
        status_code, code, message = 500, "CHAT_FAILED", "The question could not be answered."
    return JSONResponse(
        status_code=status_code, content={"error": {"code": code, "message": message}}
    )


CHAT_EXCEPTION_TYPES = (
    SessionNotFoundError,
    RetrievalNotReadyError,
    QAValidationError,
    RetrievalValidationError,
    QAProviderError,
)
