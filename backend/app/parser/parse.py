"""Safe Tree-sitter parsing for discovered repository files."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import PurePosixPath

from tree_sitter import Node, Parser
from tree_sitter_languages import get_language

from ..discovery.models import DiscoveredFile, DiscoveryResult
from ..session.models import Session
from .models import ParseDiagnostic, ParsedSymbol, ParseResult

_DECLARATION_TYPES: dict[str, frozenset[str]] = {
    "python": frozenset({"class_definition", "function_definition"}),
    "javascript": frozenset(
        {"class_declaration", "function_declaration", "method_definition", "lexical_declaration"}
    ),
    "typescript": frozenset(
        {
            "class_declaration",
            "function_declaration",
            "method_definition",
            "interface_declaration",
            "type_alias_declaration",
            "enum_declaration",
            "lexical_declaration",
        }
    ),
    "java": frozenset(
        {
            "class_declaration",
            "interface_declaration",
            "enum_declaration",
            "method_declaration",
            "constructor_declaration",
        }
    ),
    "go": frozenset({"type_declaration", "function_declaration", "method_declaration"}),
    "rust": frozenset(
        {"function_item", "struct_item", "enum_item", "trait_item", "impl_item", "type_item"}
    ),
    "c": frozenset(
        {"function_definition", "struct_specifier", "enum_specifier", "type_definition"}
    ),
    "cpp": frozenset(
        {
            "function_definition",
            "class_specifier",
            "struct_specifier",
            "enum_specifier",
            "type_definition",
        }
    ),
    "csharp": frozenset(
        {
            "class_declaration",
            "interface_declaration",
            "struct_declaration",
            "enum_declaration",
            "method_declaration",
            "local_function_statement",
        }
    ),
    "ruby": frozenset({"class", "module", "method", "singleton_method"}),
    "php": frozenset(
        {
            "class_declaration",
            "interface_declaration",
            "trait_declaration",
            "function_definition",
            "method_declaration",
        }
    ),
    "swift": frozenset(
        {
            "class_declaration",
            "protocol_declaration",
            "function_declaration",
            "initializer_declaration",
        }
    ),
    "kotlin": frozenset(
        {"class_declaration", "object_declaration", "function_declaration", "type_alias"}
    ),
}

_NAME_FIELDS = ("name", "declarator", "type", "left")


def parse_discovered_files(
    session: Session, result: DiscoveryResult | Iterable[DiscoveredFile]
) -> ParseResult:
    """Parse discovered UTF-8 files without importing or executing repository code."""

    files = result.files if isinstance(result, DiscoveryResult) else tuple(result)
    symbols: list[ParsedSymbol] = []
    diagnostics: list[ParseDiagnostic] = []
    repository = session.repository_dir.resolve()

    for discovered in files:
        relative = _normalize_relative(discovered.relative_path)
        if relative is None:
            diagnostics.append(
                ParseDiagnostic(
                    discovered.relative_path,
                    "PATH_OUTSIDE_REPOSITORY",
                    "file path is not repository-relative",
                )
            )
            continue
        path = repository.joinpath(*relative.split("/"))
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(repository)
            source = resolved.read_text(encoding="utf-8")
        except (OSError, UnicodeError, ValueError):
            diagnostics.append(
                ParseDiagnostic(
                    relative, "FILE_READ_FAILED", "source file could not be read as UTF-8"
                )
            )
            continue
        if not source:
            diagnostics.append(ParseDiagnostic(relative, "EMPTY_FILE", "source file is empty"))
            continue
        try:
            language = get_language(discovered.language)
            parser = Parser()
            parser.set_language(language)
            tree = parser.parse(source.encode("utf-8"))
        except Exception:
            diagnostics.append(
                ParseDiagnostic(relative, "GRAMMAR_UNAVAILABLE", "language grammar is unavailable")
            )
            continue

        if tree.root_node.has_error:
            diagnostics.append(
                ParseDiagnostic(relative, "SYNTAX_ERROR", "source contains syntax errors")
            )
        found = _symbols_from_tree(tree.root_node, source, relative, discovered.language)
        if found:
            symbols.extend(found)
        else:
            symbols.append(_file_symbol(relative, discovered.language, source))

    symbols.sort(
        key=lambda item: (
            item.relative_path,
            item.start_line,
            item.end_line,
            item.symbol_type,
            item.symbol_name,
        )
    )
    diagnostics.sort(key=lambda item: (item.relative_path, item.code, item.message))
    return ParseResult(tuple(symbols), tuple(diagnostics))


def _symbols_from_tree(root: Node, source: str, relative: str, language: str) -> list[ParsedSymbol]:
    nodes: list[tuple[Node, bool]] = []
    declaration_types = _DECLARATION_TYPES.get(language, frozenset())

    def is_nested_function(node: Node) -> bool:
        parent = getattr(node, "parent", None)
        while parent is not None:
            if getattr(parent, "type", None) == "class_definition":
                return True
            parent = getattr(parent, "parent", None)
        return False

    def visit(node: Node) -> None:
        node_type = node.type
        if node_type in declaration_types:
            nodes.append(
                (
                    node,
                    language == "python"
                    and node_type == "function_definition"
                    and is_nested_function(node),
                )
            )
        for child in node.children:
            visit(child)

    visit(root)
    result: list[ParsedSymbol] = []
    for node, is_method in nodes:
        start = node.start_point[0] + 1
        end = node.end_point[0] + 1
        name = _node_name(node, source) or f"anonymous_{start}"
        symbol_type = "method" if is_method else _symbol_type(node.type)
        result.append(
            ParsedSymbol(
                relative, name, symbol_type, language, _node_source(node, source), start, end
            )
        )
    return result


def _node_name(node: Node, source: str) -> str | None:
    for field in _NAME_FIELDS:
        child = node.child_by_field_name(field)
        if child is not None:
            value = _node_source(child, source).strip()
            if value:
                return value.splitlines()[0].strip(" `{}[]()")
    return None


def _node_source(node: Node, source: str) -> str:
    return source.encode("utf-8")[node.start_byte : node.end_byte].decode("utf-8")


def _symbol_type(node_type: str) -> str:
    if "method" in node_type or node_type in {"constructor_declaration", "function_definition"}:
        return "method" if "method" in node_type else "function"
    for marker in (
        "class",
        "interface",
        "struct",
        "enum",
        "trait",
        "type_alias",
        "type_item",
        "module",
    ):
        if marker in node_type:
            return marker.replace("_declaration", "")
    return "declaration"


def _file_symbol(relative: str, language: str, source: str) -> ParsedSymbol:
    lines = source.count("\n") + 1
    return ParsedSymbol(relative, PurePosixPath(relative).name, "file", language, source, 1, lines)


def _normalize_relative(value: str) -> str | None:
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or not path.parts or ".." in path.parts:
        return None
    return path.as_posix()
