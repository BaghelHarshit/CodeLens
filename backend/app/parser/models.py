"""Typed results produced by Tree-sitter parsing."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParsedSymbol:
    """A source-level declaration with repository-safe location metadata."""

    relative_path: str
    symbol_name: str
    symbol_type: str
    language: str
    source: str
    start_line: int
    end_line: int


@dataclass(frozen=True, slots=True)
class ParseDiagnostic:
    """A non-fatal issue encountered while parsing one source file."""

    relative_path: str
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class ParseResult:
    """Deterministic symbols and diagnostics for a discovery result."""

    symbols: tuple[ParsedSymbol, ...]
    diagnostics: tuple[ParseDiagnostic, ...]


__all__ = ["ParseDiagnostic", "ParseResult", "ParsedSymbol"]
