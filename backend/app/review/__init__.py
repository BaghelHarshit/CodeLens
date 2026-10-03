"""Provider-neutral code-review contracts."""

from .context import ChangedCodeContext, ReviewContext, ReviewContextLimits, build_review_context
from .diff import parse_unified_diff
from .models import (
    ChangedFile,
    DiffErrorCode,
    DiffHunk,
    DiffLine,
    ReviewFinding,
    ReviewInput,
    ReviewLimits,
    ReviewResult,
    ReviewValidationError,
    Severity,
)

__all__ = [
    "ChangedCodeContext",
    "ChangedFile",
    "DiffErrorCode",
    "DiffHunk",
    "DiffLine",
    "ReviewContext",
    "ReviewContextLimits",
    "ReviewFinding",
    "ReviewInput",
    "ReviewLimits",
    "ReviewResult",
    "ReviewValidationError",
    "Severity",
    "build_review_context",
    "parse_unified_diff",
]
