"""Tests for deterministic bounded source discovery."""

from pathlib import Path

from app.config import Settings
from app.discovery import discover_source_files
from app.session import SessionManager


def test_discovers_supported_files_in_stable_relative_order(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path / "sessions")
    session = manager.create()
    repository = session.repository_dir
    (repository / "src").mkdir()
    (repository / "src" / "z.ts").write_text("const z = 1;", encoding="utf-8")
    (repository / "src" / "a.py").write_text("print('a')", encoding="utf-8")
    (repository / "README.md").write_text("docs", encoding="utf-8")

    result = discover_source_files(session, Settings(temp_root=str(tmp_path)))

    assert [file.relative_path for file in result.files] == ["src/a.py", "src/z.ts"]
    assert [file.language for file in result.files] == ["python", "typescript"]
    assert all(str(tmp_path) not in file.relative_path for file in result.files)
    assert result.files_seen == 3
    assert result.skipped == (result.skipped[0],)
    assert result.skipped[0].reason == "unsupported_extension"


def test_skips_ignored_binary_empty_and_oversized_files(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path / "sessions")
    session = manager.create()
    repository = session.repository_dir
    (repository / "node_modules").mkdir()
    (repository / "node_modules" / "ignored.py").write_text("bad", encoding="utf-8")
    (repository / "binary.py").write_bytes(b"\x00binary")
    (repository / "empty.py").write_bytes(b"")
    (repository / "large.py").write_text("x" * 20, encoding="utf-8")
    (repository / "good.py").write_text("x = 1", encoding="utf-8")

    settings = Settings(temp_root=str(tmp_path), max_file_bytes=10)
    result = discover_source_files(session, settings)

    assert [file.relative_path for file in result.files] == ["good.py"]
    assert {item.reason for item in result.skipped} == {
        "binary",
        "empty",
        "file_too_large",
        "ignored_directory",
    }


def test_applies_file_and_byte_limits(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path / "sessions")
    session = manager.create()
    (session.repository_dir / "a.py").write_text("12345", encoding="utf-8")
    (session.repository_dir / "b.py").write_text("67890", encoding="utf-8")

    result = discover_source_files(
        session,
        Settings(temp_root=str(tmp_path), max_discovered_files=1, max_discovered_bytes=6),
    )

    assert len(result.files) == 1
    assert {item.reason for item in result.skipped} == {"file_count_limit"}
