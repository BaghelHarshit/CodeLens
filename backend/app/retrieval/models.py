"""Public models for bounded, session-scoped code retrieval."""

from __future__ import annotations

from dataclasses import dataclass


class RetrievalError(RuntimeError):
    """Base error for safe retrieval failures."""


class RetrievalValidationError(ValueError, RetrievalError):
    """Raised when retrieval input or limits are invalid."""


class RetrievalNotReadyError(RetrievalError):
    """Raised when a session does not have a ready index."""


@dataclass(frozen=True, slots=True)
class SourceReference:
    """Safe repository-relative metadata for a retrieved chunk."""

    chunk_id: str
    relative_path: str
    symbol_name: str
    symbol_type: str
    language: str
    start_line: int
    end_line: int
    score: float


@dataclass(frozen=True, slots=True)
class RetrievedContext:
    """Bounded context and references returned to a RAG workflow."""

    context: str
    references: tuple[SourceReference, ...]
    query: str

    @property
    def empty(self) -> bool:
        """Whether no indexed context matched the query."""

        return not self.references
