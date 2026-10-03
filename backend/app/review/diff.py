"""Safe unified-diff parsing for the code-review contract."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from .models import (
    ChangedFile,
    DiffErrorCode,
    DiffHunk,
    DiffLine,
    ReviewInput,
    ReviewLimits,
    ReviewValidationError,
)

_DIFF_HEADER = re.compile(r"^diff --git a/(\S+) b/(\S+)$")
_OLD_HEADER = re.compile(r"^--- (?:a/)?(.+)$")
_NEW_HEADER = re.compile(r"^\+\+\+ (?:b/)?(.+)$")
_HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?$")


def parse_unified_diff(value: str, limits: ReviewLimits | None = None) -> ReviewInput:
    """Validate and normalize a unified diff without touching the filesystem."""
    bounds = limits or ReviewLimits()
    if not isinstance(value, str):
        raise ReviewValidationError(f"{DiffErrorCode.MISSING}: diff must be text")
    if not value.strip():
        raise ReviewValidationError(f"{DiffErrorCode.EMPTY}: diff must not be empty")
    if len(value) > bounds.max_diff_chars:
        raise ReviewValidationError(f"{DiffErrorCode.OVERSIZED}: diff exceeds the maximum size")
    if "\x00" in value:
        raise ReviewValidationError(f"{DiffErrorCode.MALFORMED}: diff contains NUL bytes")

    lines = value.splitlines()
    files: list[ChangedFile] = []
    index = 0
    while index < len(lines):
        if not lines[index].startswith("diff --git "):
            raise ReviewValidationError(f"{DiffErrorCode.MALFORMED}: missing diff header")
        header = _DIFF_HEADER.fullmatch(lines[index])
        if header is None:
            raise ReviewValidationError(f"{DiffErrorCode.MALFORMED}: invalid diff header")
        old_path, new_path = header.groups()
        _validate_path(old_path)
        _validate_path(new_path)
        index += 1
        if index + 1 >= len(lines):
            raise ReviewValidationError(f"{DiffErrorCode.MALFORMED}: missing file headers")
        old_match = _OLD_HEADER.fullmatch(lines[index])
        new_match = _NEW_HEADER.fullmatch(lines[index + 1])
        if old_match is None or new_match is None:
            raise ReviewValidationError(f"{DiffErrorCode.MALFORMED}: missing file headers")
        index += 2
        hunks: list[DiffHunk] = []
        while index < len(lines) and not lines[index].startswith("diff --git "):
            if lines[index].startswith("new file mode") or lines[index].startswith(
                "deleted file mode"
            ):
                index += 1
                continue
            hunk_match = _HUNK_HEADER.fullmatch(lines[index])
            if hunk_match is None:
                raise ReviewValidationError(f"{DiffErrorCode.MALFORMED}: invalid hunk header")
            old_start, old_count, new_start, new_count = hunk_match.groups()
            old_count_value = int(old_count or 1)
            new_count_value = int(new_count or 1)
            index += 1
            hunk_lines: list[DiffLine] = []
            old_seen = new_seen = 0
            current_new = int(new_start)
            while index < len(lines) and not lines[index].startswith(("@@ ", "diff --git ")):
                raw = lines[index]
                if raw.startswith("\\ No newline at end of file"):
                    index += 1
                    continue
                if not raw or raw[0] not in " +-":
                    raise ReviewValidationError(f"{DiffErrorCode.MALFORMED}: invalid diff line")
                marker, content = raw[0], raw[1:]
                if marker == "+":
                    hunk_lines.append(DiffLine("addition", content, current_new))
                    new_seen += 1
                    current_new += 1
                elif marker == "-":
                    hunk_lines.append(DiffLine("deletion", content, None))
                    old_seen += 1
                else:
                    hunk_lines.append(DiffLine("context", content, current_new))
                    old_seen += 1
                    new_seen += 1
                    current_new += 1
                index += 1
            if old_seen != old_count_value or new_seen != new_count_value:
                raise ReviewValidationError(
                    f"{DiffErrorCode.MALFORMED}: hunk line counts do not match"
                )
            hunks.append(
                DiffHunk(
                    int(old_start),
                    old_count_value,
                    int(new_start),
                    new_count_value,
                    tuple(hunk_lines),
                )
            )
            if len(hunks) > bounds.max_hunks:
                raise ReviewValidationError(f"{DiffErrorCode.LIMIT_EXCEEDED}: too many hunks")
        if not hunks:
            raise ReviewValidationError(f"{DiffErrorCode.MALFORMED}: file has no hunks")
        path = new_path if new_path != "/dev/null" else old_path
        files.append(
            ChangedFile(
                path,
                None if old_path == "/dev/null" else old_path,
                None if new_path == "/dev/null" else new_path,
                tuple(hunks),
            )
        )
        if len(files) > bounds.max_files:
            raise ReviewValidationError(f"{DiffErrorCode.LIMIT_EXCEEDED}: too many files")
    changed_lines = sum(len(hunk.lines) for file in files for hunk in file.hunks)
    if changed_lines > bounds.max_changed_lines:
        raise ReviewValidationError(f"{DiffErrorCode.LIMIT_EXCEEDED}: too many changed lines")
    return ReviewInput("review-v1", value, tuple(files))


def _validate_path(value: str) -> None:
    if value == "/dev/null":
        return
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or not path.parts or ".." in path.parts or "\x00" in value:
        raise ReviewValidationError(f"{DiffErrorCode.UNSAFE_PATH}: diff path is unsafe")
