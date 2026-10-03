"""Bounded repository context preparation for code review."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ..indexing import IndexingRegistry
from ..retrieval import RetrievalLimits, RetrievedContext, SourceReference, for_session
from .models import ChangedFile, ReviewInput, ReviewValidationError


@dataclass(frozen=True, slots=True)
class ReviewContextLimits:
    """Bounds for review queries and the context passed to a later workflow."""

    max_queries: int = 120
    max_query_chars: int = 2_000
    max_context_chars: int = 32_000
    max_changed_chars: int = 12_000
    max_references: int = 40

    def __post_init__(self) -> None:
        if any(value < 1 for value in asdict(self).values()):
            raise ReviewValidationError("review context limits must be positive")


@dataclass(frozen=True, slots=True)
class ChangedCodeContext:
    """Diff evidence retained for review, independent of retrieval results."""

    path: str
    old_path: str | None
    new_path: str | None
    hunks: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ReviewContext:
    """Bounded changed-code evidence and related indexed repository context."""

    changed: tuple[ChangedCodeContext, ...]
    context: str
    references: tuple[SourceReference, ...]
    queries: tuple[str, ...]

    @property
    def insufficient(self) -> bool:
        """Whether the shared index yielded no related repository chunks."""

        return not self.references

    def to_dict(self) -> dict[str, Any]:
        return {
            "changed": [item.to_dict() for item in self.changed],
            "context": self.context,
            "references": [asdict(item) for item in self.references],
            "queries": list(self.queries),
            "insufficient_context": self.insufficient,
        }


def build_review_context(
    *,
    session_id: str,
    review: ReviewInput,
    registry: IndexingRegistry,
    retrieval_limits: RetrievalLimits | None = None,
    limits: ReviewContextLimits | None = None,
) -> ReviewContext:
    """Prepare diff evidence and bounded related context from the shared index."""
    if not isinstance(review, ReviewInput):
        raise ReviewValidationError("review input is invalid")
    bounds = limits or ReviewContextLimits()
    changed = tuple(_changed_context(file, bounds.max_changed_chars) for file in review.files)
    service = for_session(registry, session_id, retrieval_limits)

    references_by_id: dict[str, SourceReference] = {}
    sections: list[str] = []
    queries: list[str] = []
    used_chars = 0
    for query in _build_queries(review, bounds):
        queries.append(query)
        retrieved = service.retrieve(query)
        _merge_retrieved(retrieved, references_by_id, sections, bounds, used_chars)
        used_chars = sum(
            len(section) + (2 if index else 0) for index, section in enumerate(sections)
        )
        if len(references_by_id) >= bounds.max_references or used_chars >= bounds.max_context_chars:
            break

    references = tuple(
        sorted(
            references_by_id.values(), key=lambda reference: (-reference.score, reference.chunk_id)
        )[: bounds.max_references]
    )
    return ReviewContext(changed, "\n\n".join(sections), references, tuple(queries))


def _changed_context(file: ChangedFile, max_chars: int) -> ChangedCodeContext:
    hunks: list[dict[str, Any]] = []
    used = 0
    for hunk in file.hunks:
        lines = []
        for line in hunk.lines:
            rendered = f"{line.kind[0]}{line.content}"
            if used + len(rendered) > max_chars:
                break
            lines.append({"kind": line.kind, "content": line.content, "new_line": line.new_line})
            used += len(rendered)
        hunks.append(
            {
                "old_start": hunk.old_start,
                "old_count": hunk.old_count,
                "new_start": hunk.new_start,
                "new_count": hunk.new_count,
                "lines": lines,
            }
        )
    return ChangedCodeContext(file.path, file.old_path, file.new_path, tuple(hunks))


def _build_queries(review: ReviewInput, bounds: ReviewContextLimits) -> tuple[str, ...]:
    queries: list[str] = []
    for file in review.files:
        changed_lines = [
            line.content for hunk in file.hunks for line in hunk.lines if line.kind == "addition"
        ]
        ranges = ", ".join(
            f"{hunk.new_start}-{hunk.new_start + max(hunk.new_count - 1, 0)}" for hunk in file.hunks
        )
        detail = " ".join(changed_lines)
        queries.append(_bounded_query(f"Review {file.path} lines {ranges}: {detail}", bounds))
        if _looks_like_test(file.path):
            queries.append(
                _bounded_query(f"Related implementation and tests for {file.path}", bounds)
            )
        else:
            queries.append(_bounded_query(f"Related tests for changed file {file.path}", bounds))
        if len(queries) >= bounds.max_queries:
            break
    return tuple(queries[: bounds.max_queries])


def _bounded_query(value: str, bounds: ReviewContextLimits) -> str:
    normalized = " ".join(value.split())
    return normalized[: bounds.max_query_chars].strip()


def _looks_like_test(path: str) -> bool:
    lower = path.lower()
    return (
        lower.startswith(("test/", "tests/"))
        or "/test" in lower
        or lower.startswith("test_")
        or lower.endswith(("_test.py", ".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx"))
    )


def _merge_retrieved(
    retrieved: RetrievedContext,
    references: dict[str, SourceReference],
    sections: list[str],
    bounds: ReviewContextLimits,
    used_chars: int,
) -> None:
    for reference in retrieved.references:
        if reference.chunk_id in references or len(references) >= bounds.max_references:
            continue
        section = next(
            (
                part
                for part in retrieved.context.split("\n\n")
                if part.startswith(f"[{reference.relative_path}:{reference.start_line}-")
            ),
            "",
        )
        separator = 2 if sections else 0
        if not section:
            continue
        remaining = bounds.max_context_chars - used_chars - separator
        if remaining <= 0:
            continue
        section = section[:remaining]
        references[reference.chunk_id] = reference
        sections.append(section)
        used_chars += separator + len(section)
