"""Tests for resilient Tree-sitter parsing."""

from pathlib import Path

from app.discovery.models import DiscoveredFile, DiscoveryResult
from app.parser import parse_discovered_files
from app.session import SessionManager


def test_extracts_nested_python_symbols(tmp_path: Path) -> None:
    session = SessionManager(tmp_path / "sessions").create()
    source = (
        "class Greeter:\n    def greet(self):\n        return 1\n\ndef helper():\n    return 2\n"
    )
    (session.repository_dir / "sample.py").write_text(source, encoding="utf-8")

    result = parse_discovered_files(
        session,
        DiscoveryResult((DiscoveredFile("sample.py", "python", len(source)),), 1, len(source), ()),
    )

    assert [(item.symbol_name, item.symbol_type) for item in result.symbols] == [
        ("Greeter", "class"),
        ("greet", "method"),
        ("helper", "function"),
    ]
    assert result.symbols[1].start_line == 2
    assert result.symbols[1].end_line == 3


def test_supports_typescript_and_reports_syntax_errors(tmp_path: Path) -> None:
    session = SessionManager(tmp_path / "sessions").create()
    good = "class Calculator { add(left: number, right: number) { return left + right; } }\n"
    bad = "function valid() { return 1;\n"
    (session.repository_dir / "math.ts").write_text(good, encoding="utf-8")
    (session.repository_dir / "broken.py").write_text(bad, encoding="utf-8")
    files = (
        DiscoveredFile("broken.py", "python", len(bad)),
        DiscoveredFile("math.ts", "typescript", len(good)),
    )

    result = parse_discovered_files(session, DiscoveryResult(files, 2, len(good) + len(bad), ()))

    assert any(item.symbol_name == "Calculator" for item in result.symbols)
    assert any(
        item.code == "SYNTAX_ERROR" and item.relative_path == "broken.py"
        for item in result.diagnostics
    )


def test_empty_file_is_diagnostic_and_paths_stay_relative(tmp_path: Path) -> None:
    session = SessionManager(tmp_path / "sessions").create()
    (session.repository_dir / "empty.py").write_text("", encoding="utf-8")

    result = parse_discovered_files(
        session,
        (DiscoveredFile("empty.py", "python", 0), DiscoveredFile("../outside.py", "python", 1)),
    )

    assert result.symbols == ()
    assert {item.code for item in result.diagnostics} == {"EMPTY_FILE", "PATH_OUTSIDE_REPOSITORY"}
    assert all("sessions" not in item.relative_path for item in result.diagnostics)
