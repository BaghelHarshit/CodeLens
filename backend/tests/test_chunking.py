"""Tests for bounded, stable code chunks."""

import json

import pytest

from app.chunking import ChunkValidationError, CodeChunk, chunk_parsed_symbols
from app.parser.models import ParseDiagnostic, ParsedSymbol, ParseResult


def _symbol(source: str = "def greet():\n    return 'नमस्ते'\n") -> ParsedSymbol:
    return ParsedSymbol("src/greet.py", "greet", "function", "python", source, 3, 4)


def test_creates_stable_serializable_chunk() -> None:
    result = ParseResult((_symbol(),), (ParseDiagnostic("bad.py", "SYNTAX_ERROR", "bad"),))
    first = chunk_parsed_symbols(result)
    second = chunk_parsed_symbols(result)

    assert first == second
    assert first.chunks[0].to_dict() == CodeChunk.from_dict(first.chunks[0].to_dict()).to_dict()
    assert first.diagnostics == result.diagnostics
    assert json.dumps(first.chunks[0].to_dict(), ensure_ascii=False)


def test_splits_large_symbol_and_retains_parent_metadata() -> None:
    source = "\n".join(f"line {index}" for index in range(1, 20))
    result = chunk_parsed_symbols(
        ParseResult((_symbol(source),), ()), max_source_chars=20, overlap_lines=1
    )

    assert len(result.chunks) > 1
    assert all(item.parent_start_line == 3 and item.parent_end_line == 4 for item in result.chunks)
    assert [item.fragment_index for item in result.chunks] == list(range(len(result.chunks)))
    assert all(len(item.source) <= 20 + 7 for item in result.chunks)


def test_rejects_unsafe_or_invalid_metadata() -> None:
    with pytest.raises(ChunkValidationError):
        CodeChunk("id", "../secret.py", "x", "function", "python", "x", 1, 1, 1, 1)
    with pytest.raises(ChunkValidationError):
        CodeChunk.from_dict({"chunk_id": "only-id"})
