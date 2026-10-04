"""Security tests for ZIP repository ingestion."""

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.config import Settings
from app.repository.ingestion import IngestionError, ingest_repository
from app.session import SessionManager


def _upload(files: dict[str, str], filename: str = "repo.zip") -> UploadFile:
    archive = BytesIO()
    with ZipFile(archive, "w", ZIP_DEFLATED) as zipped:
        for name, content in files.items():
            zipped.writestr(name, content)
    archive.seek(0)
    return UploadFile(BytesIO(archive.read()), filename=filename, headers=Headers())


@pytest.mark.anyio
async def test_valid_archive_is_extracted_without_absolute_paths(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create()
    result = await ingest_repository(
        _upload({"src/main.py": "print('safe')", "node_modules/pkg.js": "ignored"}),
        session,
        Settings(temp_root=str(tmp_path)),
    )

    assert result.files_accepted == 1
    assert result.files_skipped == 1
    assert (session.repository_dir / "src/main.py").read_text(encoding="utf-8") == "print('safe')"
    assert not (session.repository_dir / "node_modules").exists()
    assert all(str(tmp_path) not in warning for warning in result.warnings)


@pytest.mark.anyio
async def test_traversal_is_rejected_and_repository_stays_empty(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create()
    upload = _upload({"../outside.txt": "unsafe"})

    with pytest.raises(IngestionError) as error:
        await ingest_repository(upload, session, Settings(temp_root=str(tmp_path)))

    assert error.value.code == "INVALID_ARCHIVE"
    assert list(session.repository_dir.iterdir()) == []
    assert not (tmp_path / "outside.txt").exists()


@pytest.mark.anyio
async def test_corrupt_upload_is_rejected(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create()
    upload = UploadFile(BytesIO(b"not a zip"), filename="repo.zip", headers=Headers())

    with pytest.raises(IngestionError) as error:
        await ingest_repository(upload, session, Settings(temp_root=str(tmp_path)))

    assert error.value.code == "INVALID_ARCHIVE"


@pytest.mark.anyio
async def test_corrupt_rar_upload_is_rejected(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.create()
    upload = UploadFile(BytesIO(b"not a rar"), filename="repo.rar", headers=Headers())

    with pytest.raises(IngestionError) as error:
        await ingest_repository(upload, session, Settings(temp_root=str(tmp_path)))

    assert error.value.code == "INVALID_ARCHIVE"
    assert list(session.repository_dir.iterdir()) == []
