"""Shared bounded retrieval service for Q&A and code review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..indexing import SearchResult, SessionIndex
from .models import (
    RetrievalNotReadyError,
    RetrievalValidationError,
    RetrievedContext,
    SourceReference,
)


class SearchableIndex(Protocol):
    """Minimal index contract required by the retrieval service."""

    @property
    def ready(self) -> bool:
        """Whether the index can accept searches."""
        ...

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        """Search the index for relevant chunks."""
        ...


@dataclass(frozen=True, slots=True)
class RetrievalLimits:
    """Hard bounds applied to every retrieval request."""

    default_top_k: int = 8
    max_top_k: int = 20
    max_query_chars: int = 4000
    max_context_chars: int = 24_000
    max_chunk_chars: int = 8_000

    def __post_init__(self) -> None:
        if (
            self.default_top_k < 1
            or self.max_top_k < self.default_top_k
            or self.max_query_chars < 1
            or self.max_context_chars < 1
            or self.max_chunk_chars < 1
        ):
            raise RetrievalValidationError("retrieval limits are invalid")


class RetrievalService:
    """Retrieve bounded, metadata-rich context from one session index."""

    def __init__(self, index: SearchableIndex, limits: RetrievalLimits | None = None) -> None:
        self._index = index
        self._limits = limits or RetrievalLimits()

    @property
    def index(self) -> SearchableIndex:
        """Expose the underlying session index for shared-workflow identity checks."""

        return self._index

    def retrieve(self, query: str, top_k: int | None = None) -> RetrievedContext:
        """Embed and search a query, returning bounded context and safe references."""
        normalized_query = self._validate_query(query)
        requested_top_k = self._validate_top_k(top_k)
        if not self._index.ready:
            raise RetrievalNotReadyError("repository retrieval is not ready")

        results = self._index.search(normalized_query, requested_top_k)
        references: list[SourceReference] = []
        sections: list[str] = []
        seen: set[str] = set()
        used_chars = 0
        for result in results:
            chunk = result.chunk
            if chunk.chunk_id in seen:
                continue
            source = chunk.source[: self._limits.max_chunk_chars]
            reference = SourceReference(
                chunk_id=chunk.chunk_id,
                relative_path=chunk.relative_path,
                symbol_name=chunk.symbol_name,
                symbol_type=chunk.symbol_type,
                language=chunk.language,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                score=result.score,
            )
            section = self._format_section(reference, source)
            separator_length = 2 if sections else 0
            if used_chars + separator_length + len(section) > self._limits.max_context_chars:
                break
            seen.add(chunk.chunk_id)
            references.append(reference)
            sections.append(section)
            used_chars += separator_length + len(section)

        return RetrievedContext(
            context="\n\n".join(sections), references=tuple(references), query=normalized_query
        )

    def _validate_query(self, query: str) -> str:
        if not isinstance(query, str):
            raise RetrievalValidationError("query must be text")
        normalized = query.strip()
        if not normalized:
            raise RetrievalValidationError("query must not be empty")
        if len(normalized) > self._limits.max_query_chars:
            raise RetrievalValidationError("query exceeds the maximum length")
        return normalized

    def _validate_top_k(self, top_k: int | None) -> int:
        value = self._limits.default_top_k if top_k is None else top_k
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or not 1 <= value <= self._limits.max_top_k
        ):
            raise RetrievalValidationError("top_k is outside the allowed range")
        return value

    @staticmethod
    def _format_section(reference: SourceReference, source: str) -> str:
        return (
            f"[{reference.relative_path}:{reference.start_line}-{reference.end_line}] "
            f"{reference.symbol_type} {reference.symbol_name} ({reference.language})\n{source}"
        )


def retrieval_service(
    index: SessionIndex, limits: RetrievalLimits | None = None
) -> RetrievalService:
    """Construct the shared service around an existing session index."""

    return RetrievalService(index, limits)
