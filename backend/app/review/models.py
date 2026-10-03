"""Provider-neutral models for bounded code-review contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from ..chunking.models import _validate_relative_path


class ReviewValidationError(ValueError):
    """Raised when review input or output violates the public contract."""


class DiffErrorCode(str, Enum):  # noqa: UP042
    """Stable validation categories for later API and graph layers."""

    MISSING = "MISSING_DIFF"
    EMPTY = "EMPTY_DIFF"
    OVERSIZED = "DIFF_TOO_LARGE"
    MALFORMED = "MALFORMED_DIFF"
    UNSAFE_PATH = "UNSAFE_DIFF_PATH"
    LIMIT_EXCEEDED = "DIFF_LIMIT_EXCEEDED"


class Severity(str, Enum):  # noqa: UP042
    """Normalized review finding severity."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class ReviewLimits:
    """Resource bounds for diff parsing and finding text."""

    max_diff_chars: int = 200_000
    max_files: int = 100
    max_hunks: int = 500
    max_changed_lines: int = 10_000
    max_text_chars: int = 4_000

    def __post_init__(self) -> None:
        if any(value < 1 for value in asdict(self).values()):
            raise ReviewValidationError("review limits must be positive")


@dataclass(frozen=True, slots=True)
class DiffLine:
    """One changed or context line with normalized new-file location."""

    kind: str
    content: str
    new_line: int | None

    def __post_init__(self) -> None:
        if self.kind not in {"addition", "deletion", "context"}:
            raise ReviewValidationError("diff line kind is invalid")
        if self.new_line is not None and self.new_line < 1:
            raise ReviewValidationError("diff line number is invalid")


@dataclass(frozen=True, slots=True)
class DiffHunk:
    """A unified-diff hunk and its normalized line records."""

    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: tuple[DiffLine, ...]

    def __post_init__(self) -> None:
        if min(self.old_start, self.new_start) < 1 or min(self.old_count, self.new_count) < 0:
            raise ReviewValidationError("diff hunk range is invalid")


@dataclass(frozen=True, slots=True)
class ChangedFile:
    """A repository-relative file represented in a unified diff."""

    path: str
    old_path: str | None
    new_path: str | None
    hunks: tuple[DiffHunk, ...]

    def __post_init__(self) -> None:
        _validate_relative_path(self.path)
        for path in (self.old_path, self.new_path):
            if path is not None:
                _validate_relative_path(path)
        if not self.hunks:
            raise ReviewValidationError("changed file must contain a hunk")


@dataclass(frozen=True, slots=True)
class ReviewInput:
    """Versioned normalized review input consumed by later workflow stages."""

    schema_version: str
    diff: str
    files: tuple[ChangedFile, ...]

    def __post_init__(self) -> None:
        if self.schema_version != "review-v1":
            raise ReviewValidationError("unsupported review schema version")
        if not self.diff.strip() or not self.files:
            raise ReviewValidationError("review input must contain a diff and files")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ReviewFinding:
    """Structured, evidence-oriented code-review finding."""

    severity: Severity
    file: str
    line: int
    issue: str
    explanation: str
    suggested_fix: str | None = None
    category: str | None = None
    confidence: float | None = None

    def __post_init__(self) -> None:
        _validate_relative_path(self.file)
        if self.line < 1:
            raise ReviewValidationError("finding line must be positive")
        for name, value in (("issue", self.issue), ("explanation", self.explanation)):
            if not isinstance(value, str) or not value.strip() or len(value) > 4_000:
                raise ReviewValidationError(f"finding {name} is invalid")
        for name, value in (("suggested_fix", self.suggested_fix), ("category", self.category)):
            if value is not None and (not value.strip() or len(value) > 256):
                raise ReviewValidationError(f"finding {name} is invalid")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ReviewValidationError("finding confidence must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"severity": self.severity.value}


@dataclass(frozen=True, slots=True)
class ReviewResult:
    """Terminal review result shape for valid, empty, or insufficient outcomes."""

    outcome: str
    findings: tuple[ReviewFinding, ...] = ()

    def __post_init__(self) -> None:
        if self.outcome not in {"findings", "no_findings", "insufficient_context"}:
            raise ReviewValidationError("review outcome is invalid")
        if self.outcome == "findings" and not self.findings:
            raise ReviewValidationError("findings outcome requires findings")
        if self.outcome != "findings" and self.findings:
            raise ReviewValidationError("terminal outcome cannot contain findings")

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "findings": [finding.to_dict() for finding in self.findings],
        }
