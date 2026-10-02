"""Typed, serializable code-chunk metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any


class ChunkValidationError(ValueError):
    """Raised when chunk metadata is unsafe or inconsistent."""


@dataclass(frozen=True, slots=True)
class CodeChunk:
    """A bounded source chunk with stable retrieval metadata."""

    chunk_id: str
    relative_path: str
    symbol_name: str
    symbol_type: str
    language: str
    source: str
    start_line: int
    end_line: int
    parent_start_line: int
    parent_end_line: int
    fragment_index: int = 0
    fragment_count: int = 1

    def __post_init__(self) -> None:
        _validate_relative_path(self.relative_path)
        if not self.chunk_id or self.start_line < 1 or self.end_line < self.start_line:
            raise ChunkValidationError("chunk identity or line range is invalid")
        if self.parent_start_line < 1 or self.parent_end_line < self.parent_start_line:
            raise ChunkValidationError("parent line range is invalid")
        if not 0 <= self.fragment_index < self.fragment_count:
            raise ChunkValidationError("fragment metadata is invalid")
        if not self.source:
            raise ChunkValidationError("chunk source cannot be empty")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible public representation."""

        return {
            "chunk_id": self.chunk_id,
            "relative_path": self.relative_path,
            "symbol_name": self.symbol_name,
            "symbol_type": self.symbol_type,
            "language": self.language,
            "source": self.source,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "parent_start_line": self.parent_start_line,
            "parent_end_line": self.parent_end_line,
            "fragment_index": self.fragment_index,
            "fragment_count": self.fragment_count,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> CodeChunk:
        """Validate and restore a serialized chunk."""

        required = {
            "chunk_id",
            "relative_path",
            "symbol_name",
            "symbol_type",
            "language",
            "source",
            "start_line",
            "end_line",
            "parent_start_line",
            "parent_end_line",
        }
        if not required.issubset(value):
            raise ChunkValidationError("chunk metadata is incomplete")
        try:
            return cls(**{key: value[key] for key in cls.__dataclass_fields__})
        except (KeyError, TypeError, ValueError) as exc:
            raise ChunkValidationError("chunk metadata is invalid") from exc


def _validate_relative_path(value: str) -> None:
    path = PurePosixPath(value.replace("\\", "/"))
    if not value or path.is_absolute() or not path.parts or ".." in path.parts:
        raise ChunkValidationError("path must be repository-relative")


@dataclass(frozen=True, slots=True)
class ChunkingResult:
    """Chunks plus diagnostics retained from parsing."""

    chunks: tuple[CodeChunk, ...]
    diagnostics: tuple[Any, ...] = ()


__all__ = ["ChunkValidationError", "ChunkingResult", "CodeChunk"]
