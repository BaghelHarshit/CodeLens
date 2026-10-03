"""Provider-neutral code-review contracts."""

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
    "ChangedFile",
    "DiffErrorCode",
    "DiffHunk",
    "DiffLine",
    "ReviewFinding",
    "ReviewInput",
    "ReviewLimits",
    "ReviewResult",
    "ReviewValidationError",
    "Severity",
    "parse_unified_diff",
]
