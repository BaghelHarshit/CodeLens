"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api_repository import (
    REPOSITORY_EXCEPTION_TYPES,
    repository_exception_handler,
)
from .api_repository import (
    router as repository_router,
)
from .api_session import (
    SESSION_EXCEPTION_TYPES,
    session_exception_handler,
)
from .api_session import (
    router as session_router,
)
from .config import get_settings
from .session import SessionManager

settings = get_settings()

app = FastAPI(
    title="CodeLens API",
    description="Session-based repository intelligence and code review API.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
app.state.settings = settings
app.state.session_manager = SessionManager(settings.temp_root)
for exception_type in (*SESSION_EXCEPTION_TYPES, *REPOSITORY_EXCEPTION_TYPES):
    handler = (
        session_exception_handler
        if exception_type in SESSION_EXCEPTION_TYPES
        else repository_exception_handler
    )
    app.add_exception_handler(exception_type, handler)
app.include_router(session_router)
app.include_router(repository_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Report that the API process is available."""

    return {"status": "ok"}


@app.get("/api/health", tags=["system"])
def api_health() -> dict[str, str]:
    """Provide the versioned health endpoint used by the frontend."""

    return {"status": "ok"}
