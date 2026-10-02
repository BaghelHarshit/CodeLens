"""Deterministic symbol-aware source chunking."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

from ..parser.models import ParsedSymbol, ParseResult
from .models import ChunkingResult, CodeChunk

_CHUNK_ID_VERSION = "chunk-v1"


def chunk_parsed_symbols(
    result: ParseResult | Iterable[ParsedSymbol],
    *,
    max_source_chars: int = 4000,
    overlap_lines: int = 1,
) -> ChunkingResult:
    """Create bounded chunks while preserving symbol and line metadata."""

    if max_source_chars < 1 or overlap_lines < 0:
        raise ValueError("chunk limits must be positive")
    symbols = result.symbols if isinstance(result, ParseResult) else tuple(result)
    chunks: list[CodeChunk] = []
    for symbol in symbols:
        parts = _split_source(symbol, max_source_chars, overlap_lines)
        count = len(parts)
        for index, (source, start_line, end_line) in enumerate(parts):
            chunk_id = _stable_id(symbol, index)
            chunks.append(
                CodeChunk(
                    chunk_id=chunk_id,
                    relative_path=symbol.relative_path,
                    symbol_name=symbol.symbol_name,
                    symbol_type=symbol.symbol_type,
                    language=symbol.language,
                    source=source,
                    start_line=start_line,
                    end_line=end_line,
                    parent_start_line=symbol.start_line,
                    parent_end_line=symbol.end_line,
                    fragment_index=index,
                    fragment_count=count,
                )
            )
    chunks.sort(
        key=lambda item: (item.relative_path, item.start_line, item.end_line, item.chunk_id)
    )
    diagnostics = result.diagnostics if isinstance(result, ParseResult) else ()
    return ChunkingResult(tuple(chunks), tuple(diagnostics))


def _split_source(
    symbol: ParsedSymbol, max_chars: int, overlap_lines: int
) -> list[tuple[str, int, int]]:
    if len(symbol.source) <= max_chars:
        return [(symbol.source, symbol.start_line, symbol.end_line)]
    lines = symbol.source.splitlines(keepends=True)
    parts: list[tuple[str, int, int]] = []
    cursor = 0
    while cursor < len(lines):
        end = cursor
        size = 0
        while end < len(lines) and (size + len(lines[end]) <= max_chars or end == cursor):
            size += len(lines[end])
            end += 1
        source = "".join(lines[cursor:end])
        start_line = symbol.start_line + cursor
        end_line = start_line + source.count("\n") - (0 if source.endswith("\n") else 1)
        if end_line < start_line:
            end_line = start_line
        parts.append((source, start_line, max(start_line, min(end_line, symbol.end_line))))
        next_cursor = end - overlap_lines
        cursor = max(cursor + 1, next_cursor)
    return parts


def _stable_id(symbol: ParsedSymbol, fragment_index: int) -> str:
    identity = "\x1f".join(
        (
            _CHUNK_ID_VERSION,
            symbol.relative_path,
            symbol.language,
            symbol.symbol_name,
            symbol.symbol_type,
            str(symbol.start_line),
            str(symbol.end_line),
            str(fragment_index),
        )
    )
    return f"{_CHUNK_ID_VERSION}-{hashlib.sha256(identity.encode('utf-8')).hexdigest()}"


__all__ = ["chunk_parsed_symbols"]
