"""Bounded and non-executing ZIP repository ingestion."""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from fastapi import UploadFile

from ..config import Settings
from ..session.models import Session


class IngestionError(Exception):
    """A safe, client-facing repository ingestion failure."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class IngestionResult:
    """Safe summary of an accepted repository archive."""

    files_accepted: int
    files_skipped: int
    extracted_bytes: int
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Member:
    info: zipfile.ZipInfo
    relative_path: PurePosixPath


async def ingest_repository(
    upload: UploadFile, session: Session, settings: Settings
) -> IngestionResult:
    """Validate and atomically extract a ZIP upload into a session repository."""

    if session.repository_dir.exists() and any(session.repository_dir.iterdir()):
        raise IngestionError(
            "INVALID_SESSION_STATE", "Repository replacement is not supported.", 409
        )

    if not upload.filename or Path(upload.filename).suffix.lower() != ".zip":
        raise IngestionError("UNSUPPORTED_ARCHIVE", "Only ZIP repository uploads are supported.")

    staging_dir = Path(tempfile.mkdtemp(prefix="repository-", dir=session.root))
    archive_path = staging_dir / "upload.zip"
    extraction_dir = staging_dir / "extracted"
    extraction_dir.mkdir()
    try:
        await _save_upload(upload, archive_path, settings.max_repository_bytes)
        result = _extract_archive(archive_path, extraction_dir, settings)
        if result.files_accepted == 0:
            raise IngestionError(
                "EMPTY_REPOSITORY", "The archive contains no usable repository files."
            )
        _replace_repository(session.repository_dir, extraction_dir)
        return result
    except IngestionError:
        raise
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise IngestionError(
            "INVALID_ARCHIVE", "The uploaded file is not a valid ZIP archive."
        ) from exc
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


async def _save_upload(upload: UploadFile, destination: Path, limit: int) -> None:
    """Stream the upload to disk without exceeding the compressed limit."""

    total = 0
    with destination.open("wb") as output:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                raise IngestionError("UPLOAD_TOO_LARGE", "The uploaded archive is too large.", 413)
            output.write(chunk)


def _extract_archive(
    archive_path: Path, extraction_dir: Path, settings: Settings
) -> IngestionResult:
    """Validate archive members and extract regular files explicitly."""

    warnings: list[str] = []
    accepted = 0
    skipped = 0
    extracted_bytes = 0
    seen: set[str] = set()
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.infolist()
            if not members:
                raise IngestionError("INVALID_ARCHIVE", "The uploaded archive is empty.")
            if len(members) > settings.max_extracted_files:
                raise IngestionError(
                    "EXTRACTION_LIMIT_EXCEEDED", "The archive contains too many files.", 413
                )
            validated: list[_Member] = []
            for info in members:
                relative = _safe_member_path(info.filename, settings)
                key = relative.as_posix()
                if key in seen:
                    raise IngestionError("INVALID_ARCHIVE", "The archive contains colliding paths.")
                seen.add(key)
                if info.is_dir():
                    continue
                _ensure_regular_file(info)
                if _is_ignored(relative, settings.ignored_directories):
                    skipped += 1
                    warnings.append(f"Skipped ignored path: {key}")
                    continue
                if info.file_size > settings.max_file_bytes:
                    skipped += 1
                    warnings.append(f"Skipped oversized file: {key}")
                    continue
                extracted_bytes += info.file_size
                if extracted_bytes > settings.max_extracted_bytes:
                    raise IngestionError(
                        "EXTRACTION_LIMIT_EXCEEDED", "The extracted repository is too large.", 413
                    )
                validated.append(_Member(info, relative))

            for member in validated:
                target = extraction_dir.joinpath(*member.relative_path.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member.info, "r") as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
                accepted += 1
    except zipfile.BadZipFile as exc:
        raise IngestionError(
            "INVALID_ARCHIVE", "The uploaded file is not a valid ZIP archive."
        ) from exc
    return IngestionResult(accepted, skipped, extracted_bytes, tuple(warnings))


def _safe_member_path(name: str, settings: Settings) -> PurePosixPath:
    """Normalize one archive name and reject filesystem escape attempts."""

    if "\x00" in name:
        raise IngestionError("INVALID_ARCHIVE", "The archive contains an invalid path.")
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise IngestionError("INVALID_ARCHIVE", "The archive contains an unsafe path.")
    if len(normalized) > settings.max_archive_path_length:
        raise IngestionError("EXTRACTION_LIMIT_EXCEEDED", "An archive path is too long.", 413)
    if len(path.parts) > settings.max_archive_nesting:
        raise IngestionError(
            "EXTRACTION_LIMIT_EXCEEDED", "An archive path is too deeply nested.", 413
        )
    return path


def _ensure_regular_file(info: zipfile.ZipInfo) -> None:
    """Reject links and special entries encoded in ZIP external attributes."""

    mode = (info.external_attr >> 16) & 0xFFFF
    if mode and stat.S_IFMT(mode) not in {0, stat.S_IFREG}:
        raise IngestionError("INVALID_ARCHIVE", "The archive contains an unsupported file type.")


def _is_ignored(path: PurePosixPath, ignored_directories: frozenset[str]) -> bool:
    return any(part in ignored_directories for part in path.parts[:-1])


def _replace_repository(repository_dir: Path, extraction_dir: Path) -> None:
    """Replace the empty session repository with validated extracted data."""

    repository_dir.mkdir(parents=True, exist_ok=True)
    for child in repository_dir.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
    for child in extraction_dir.iterdir():
        os.replace(child, repository_dir / child.name)
