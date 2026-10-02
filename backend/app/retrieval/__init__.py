"""Shared session-scoped retrieval for repository RAG workflows."""

from .models import (
    RetrievalError,
    RetrievalNotReadyError,
    RetrievalValidationError,
    RetrievedContext,
    SourceReference,
)
from .registry import for_session
from .service import RetrievalLimits, RetrievalService, retrieval_service

__all__ = [
    "RetrievedContext",
    "RetrievalError",
    "RetrievalLimits",
    "RetrievalNotReadyError",
    "RetrievalService",
    "RetrievalValidationError",
    "SourceReference",
    "for_session",
    "retrieval_service",
]
