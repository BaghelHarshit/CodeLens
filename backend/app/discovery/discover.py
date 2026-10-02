"""Deterministic, bounded source-file discovery."""

from __future__ import annotations

import os
from collections import Counter
from pathlib import Path, PurePosixPath

from ..config import Settings
from ..session.models import Session
from .models import DiscoveredFile, DiscoveryResult, SkipReason

SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
}
_PREFIX_BYTES = 8192


def discover_source_files(session: Session, settings: Settings) -> DiscoveryResult:
    """Find supported, readable source files without executing repository data."""

    repository = session.repository_dir.resolve()
    if not repository.is_dir() or repository.is_symlink():
        return DiscoveryResult((), 0, 0, (SkipReason("missing_repository", 1),))

    files: list[DiscoveredFile] = []
    reasons: Counter[str] = Counter()
    files_seen = 0
    bytes_indexed = 0
    stopped = False

    for current_root, directory_names, file_names in os.walk(
        repository, topdown=True, followlinks=False
    ):
        current = Path(current_root)
        directory_names.sort()
        file_names.sort()
        retained_directories: list[str] = []
        for name in directory_names:
            directory = current / name
            if name in settings.ignored_directories:
                reasons["ignored_directory"] += 1
            elif directory.is_symlink():
                reasons["symlink"] += 1
            else:
                retained_directories.append(name)
        directory_names[:] = retained_directories

        for name in file_names:
            files_seen += 1
            candidate = current / name
            relative = _relative_path(candidate, repository)
            if relative is None:
                reasons["outside_repository"] += 1
                continue
            if candidate.is_symlink():
                reasons["symlink"] += 1
                continue
            if not candidate.is_file():
                reasons["not_regular_file"] += 1
                continue
            language = SUPPORTED_EXTENSIONS.get(candidate.suffix.lower())
            if language is None:
                reasons["unsupported_extension"] += 1
                continue
            try:
                size = candidate.stat().st_size
            except OSError:
                reasons["unreadable"] += 1
                continue
            if size == 0:
                reasons["empty"] += 1
                continue
            if size > settings.max_file_bytes:
                reasons["file_too_large"] += 1
                continue
            if len(files) >= settings.max_discovered_files:
                reasons["file_count_limit"] += 1
                stopped = True
                break
            if bytes_indexed + size > settings.max_discovered_bytes:
                reasons["byte_limit"] += 1
                continue
            if _looks_binary(candidate):
                reasons["binary"] += 1
                continue
            files.append(DiscoveredFile(relative, language, size))
            bytes_indexed += size
        if stopped:
            break

    ordered_reasons = tuple(SkipReason(reason, reasons[reason]) for reason in sorted(reasons))
    return DiscoveryResult(tuple(files), files_seen, bytes_indexed, ordered_reasons)


def _relative_path(candidate: Path, repository: Path) -> str | None:
    try:
        relative = candidate.resolve(strict=False).relative_to(repository)
    except ValueError:
        return None
    if not relative.parts:
        return None
    return PurePosixPath(*relative.parts).as_posix()


def _looks_binary(path: Path) -> bool:
    try:
        prefix = path.read_bytes()[:_PREFIX_BYTES]
    except OSError:
        return True
    if b"\x00" in prefix:
        return True
    try:
        prefix.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False
