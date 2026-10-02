"""Typed source-file discovery results."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DiscoveredFile:
    """A supported source file identified by a repository-relative path."""

    relative_path: str
    language: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class SkipReason:
    """A deterministic count of files omitted during discovery."""

    reason: str
    count: int


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    """Bounded, deterministic source discovery output."""

    files: tuple[DiscoveredFile, ...]
    files_seen: int
    bytes_indexed: int
    skipped: tuple[SkipReason, ...]
