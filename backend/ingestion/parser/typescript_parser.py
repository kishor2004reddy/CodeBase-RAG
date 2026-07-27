"""
ingestion/parser/typescript_parser.py
-------------------------------------
Parses TypeScript / TSX source files using tree-sitter to extract:
  - Functions (regular + arrow functions assigned to const/let)
  - Classes (with methods and properties)
  - Interfaces
  - Import relationships
  - Export relationships
  - Call relationships
  - Inheritance (extends / implements)

Returns a ParsedFile containing all symbols and relationships.
"""

import tree_sitter_typescript as tstypescript
from tree_sitter import Language, Parser, Node

from core.logging import get_logger
from ingestion.parser.models import (
    Language as LangEnum,
    ParsedFile,
    ParsedRelationship,
    ParsedSymbol,
    RelationshipType,
    SymbolType,
)

logger = get_logger(__name__)

# ── Tree-sitter setup ────────────────────────────────────────────────────────

# tree-sitter-typescript exposes both typescript and tsx grammars
TS_LANGUAGE = Language(tstypescript.language_typescript())
TSX_LANGUAGE = Language(tstypescript.language_tsx())


def _make_parser(tsx: bool = False) -> Parser:
    """Create a tree-sitter parser for TypeScript or TSX."""
    lang = TSX_LANGUAGE if tsx else TS_LANGUAGE
    parser = Parser(lang)
    return parser


# ── Public API ────────────────────────────────────────────────────────────────


def parse_typescript_file(source_code: str, file_path: str) -> ParsedFile:
    """
    Parse a single TypeScript/TSX file and extract symbols + relationships.

    Parameters
    ----------
    source_code : str
        The raw file contents.
    file_path : str
        Relative path within the repo.

    Returns
    -------
    ParsedFile
        All symbols and relationships found in this file.
    """
    is_tsx = file_path.endswith(".tsx")
    source_bytes = source_code.encode("utf-8")
    parser = _make_parser(tsx=is_tsx)
    tree = parser.parse(source_bytes)
    root = tree.root_node

    symbols: list[ParsedSymbol] = []
    relationships: list[ParsedRelationship] = []

    # Walk top-level children
    for child in root.children:
        _process_node(child, source_bytes, file_path, symbols, relationships)

    # Extract function calls from the entire file
    call_rels = _extract_calls(root, source_bytes, file_path)
    relationships.extend(call_rels)

    loc = source_code.count("\n") + (1 if source_code and not source_code.endswith("\n") else 0)

    logger.debug(
        "Parsed %s: %d symbols, %d relationships, %d LOC",
        file_path, len(symbols), len(relationships), loc,
    )

    return ParsedFile(
        file_path=file_path,
        language=LangEnum.TYPESCRIPT,
        symbols=symbols,
        relationships=relationships,
        lines_of_code=loc,
    )


# ── Node processing ──────────────────────────────────────────────────────────


def _process_node(
    node: Node,
    source: bytes,
    file_path: str,
    symbols: list[ParsedSymbol],
    relationships: list[ParsedRelationship],
) -> None:
    """Route a top-level node to the right extractor."""

    ntype = node.type

    # ── function_declaration: function foo() {} ───────────────────────
    if ntype == "function_declaration":
        sym = _extract_function(node, source, file_path)
        if sym:
            symbols.append(sym)
            relationships.append(ParsedRelationship(
                source=file_path,
                target=sym.name,
                relationship=RelationshipType.DEFINES,
                file_path=file_path,
            ))

    # ── class_declaration: class Foo {} ───────────────────────────────
    elif ntype == "class_declaration":
        class_syms, class_rels = _extract_class(node, source, file_path)
        symbols.extend(class_syms)
        relationships.extend(class_rels)

    # ── interface_declaration: interface Bar {} ───────────────────────
    elif ntype == "interface_declaration":
        sym = _extract_interface(node, source, file_path)
        if sym:
            symbols.append(sym)
            relationships.append(ParsedRelationship(
                source=file_path,
                target=sym.name,
                relationship=RelationshipType.DEFINES,
                file_path=file_path,
            ))

    # ── export_statement: export function / export class / export default
    elif ntype == "export_statement":
        _process_export(node, source, file_path, symbols, relationships)

    # ── import_statement: import { X } from 'Y' ──────────────────────
    elif ntype == "import_statement":
        rels = _extract_import(node, source, file_path)
        relationships.extend(rels)

    # ── lexical_declaration: const foo = () => {} (arrow functions) ───
    elif ntype in ("lexical_declaration", "variable_declaration"):
        arrow_syms = _extract_arrow_functions(node, source, file_path)
        for sym in arrow_syms:
            symbols.append(sym)
            relationships.append(ParsedRelationship(
                source=file_path,
                target=sym.name,
                relationship=RelationshipType.DEFINES,
                file_path=file_path,
            ))


# ── Function extraction ──────────────────────────────────────────────────────


def _extract_function(
    node: Node,
    source: bytes,
    file_path: str,
    parent_class: str | None = None,
) -> ParsedSymbol | None:
    """Extract a function_declaration node."""
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None

    name = _node_text(name_node, source)
    sym_type = SymbolType.METHOD if parent_class else SymbolType.FUNCTION

    return ParsedSymbol(
        name=name,
        symbol_type=sym_type,
        language=LangEnum.TYPESCRIPT,
        file_path=file_path,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        source_code=_node_text(node, source),
        docstring=_extract_jsdoc(node, source),
        parent_class=parent_class,
        signature=_extract_function_sig(node, source),
    )


# ── Arrow function extraction ────────────────────────────────────────────────


def _extract_arrow_functions(
    node: Node,
    source: bytes,
    file_path: str,
) -> list[ParsedSymbol]:
    """
    Extract arrow functions from const/let declarations.

    Matches patterns like:
      const handleClick = (e: Event) => { ... }
      export const fetchData = async () => { ... }
    """
    symbols: list[ParsedSymbol] = []

    for child in node.children:
        if child.type == "variable_declarator":
            name_node = child.child_by_field_name("name")
            value_node = child.child_by_field_name("value")

            if name_node and value_node and value_node.type == "arrow_function":
                name = _node_text(name_node, source)
                symbols.append(ParsedSymbol(
                    name=name,
                    symbol_type=SymbolType.FUNCTION,
                    language=LangEnum.TYPESCRIPT,
                    file_path=file_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    source_code=_node_text(node, source),
                    docstring=_extract_jsdoc(node, source),
                    signature=f"const {name} = {_extract_arrow_sig(value_node, source)}",
                ))

    return symbols


# ── Class extraction ─────────────────────────────────────────────────────────


def _extract_class(
    node: Node,
    source: bytes,
    file_path: str,
) -> tuple[list[ParsedSymbol], list[ParsedRelationship]]:
    """Extract a class declaration — the class itself plus its methods."""
    symbols: list[ParsedSymbol] = []
    relationships: list[ParsedRelationship] = []

    name_node = node.child_by_field_name("name")
    if name_node is None:
        return symbols, relationships

    class_name = _node_text(name_node, source)

    # Class symbol
    class_sym = ParsedSymbol(
        name=class_name,
        symbol_type=SymbolType.CLASS,
        language=LangEnum.TYPESCRIPT,
        file_path=file_path,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        source_code=_node_text(node, source),
        docstring=_extract_jsdoc(node, source),
        signature=_extract_class_sig(node, source),
    )
    symbols.append(class_sym)

    # File DEFINES this class
    relationships.append(ParsedRelationship(
        source=file_path,
        target=class_name,
        relationship=RelationshipType.DEFINES,
        file_path=file_path,
    ))

    # ── Heritage: extends / implements ────────────────────────────────
    for child in node.children:
        if child.type == "class_heritage":
            heritage_text = _node_text(child, source)
            for sub in child.children:
                if sub.type == "extends_clause":
                    base = _find_identifier(sub, source)
                    if base:
                        relationships.append(ParsedRelationship(
                            source=class_name,
                            target=base,
                            relationship=RelationshipType.INHERITS,
                            file_path=file_path,
                        ))
                elif sub.type == "implements_clause":
                    for impl_child in sub.children:
                        if impl_child.type in ("type_identifier", "generic_type"):
                            iface = _node_text(impl_child, source).split("<")[0]
                            relationships.append(ParsedRelationship(
                                source=class_name,
                                target=iface,
                                relationship=RelationshipType.INHERITS,
                                file_path=file_path,
                            ))

    # ── Methods inside the class body ─────────────────────────────────
    body = node.child_by_field_name("body")
    if body:
        for child in body.children:
            if child.type == "method_definition":
                method = _extract_method(child, source, file_path, class_name)
                if method:
                    symbols.append(method)

    return symbols, relationships


def _extract_method(
    node: Node,
    source: bytes,
    file_path: str,
    parent_class: str,
) -> ParsedSymbol | None:
    """Extract a method_definition inside a class body."""
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None

    name = _node_text(name_node, source)

    return ParsedSymbol(
        name=name,
        symbol_type=SymbolType.METHOD,
        language=LangEnum.TYPESCRIPT,
        file_path=file_path,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        source_code=_node_text(node, source),
        docstring=_extract_jsdoc(node, source),
        parent_class=parent_class,
        signature=_extract_method_sig(node, source),
    )


# ── Interface extraction ─────────────────────────────────────────────────────


def _extract_interface(
    node: Node,
    source: bytes,
    file_path: str,
) -> ParsedSymbol | None:
    """Extract an interface_declaration."""
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None

    return ParsedSymbol(
        name=_node_text(name_node, source),
        symbol_type=SymbolType.INTERFACE,
        language=LangEnum.TYPESCRIPT,
        file_path=file_path,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        source_code=_node_text(node, source),
        docstring=_extract_jsdoc(node, source),
    )


# ── Export processing ─────────────────────────────────────────────────────────


def _process_export(
    node: Node,
    source: bytes,
    file_path: str,
    symbols: list[ParsedSymbol],
    relationships: list[ParsedRelationship],
) -> None:
    """
    Handle export_statement — it wraps another declaration.
    e.g. export function foo() {}, export class Bar {}, export const x = ...
    """
    for child in node.children:
        # Recursively process the inner declaration
        _process_node(child, source, file_path, symbols, relationships)

    # Add EXPORTS relationships for any symbols defined inside
    # (the inner _process_node already adds DEFINES)
    for child in node.children:
        name = None
        if child.type in ("function_declaration", "class_declaration", "interface_declaration"):
            name_node = child.child_by_field_name("name")
            if name_node:
                name = _node_text(name_node, source)
        elif child.type in ("lexical_declaration", "variable_declaration"):
            for vd in child.children:
                if vd.type == "variable_declarator":
                    name_node = vd.child_by_field_name("name")
                    if name_node:
                        name = _node_text(name_node, source)

        if name:
            relationships.append(ParsedRelationship(
                source=file_path,
                target=name,
                relationship=RelationshipType.EXPORTS,
                file_path=file_path,
            ))


# ── Import extraction ────────────────────────────────────────────────────────


def _extract_import(node: Node, source: bytes, file_path: str) -> list[ParsedRelationship]:
    """Extract the module source from an import statement."""
    relationships: list[ParsedRelationship] = []

    source_node = node.child_by_field_name("source")
    if source_node:
        # The source is a string like './utils' or 'react'
        module = _node_text(source_node, source).strip("'\"")
        relationships.append(ParsedRelationship(
            source=file_path,
            target=module,
            relationship=RelationshipType.IMPORTS,
            file_path=file_path,
        ))

    return relationships


# ── Call extraction ───────────────────────────────────────────────────────────


def _extract_calls(root: Node, source: bytes, file_path: str) -> list[ParsedRelationship]:
    """Walk the AST and find function calls."""
    relationships: list[ParsedRelationship] = []
    seen: set[str] = set()

    def _walk(node: Node) -> None:
        if node.type == "call_expression":
            func_node = node.child_by_field_name("function")
            if func_node:
                call_name = _node_text(func_node, source)
                if call_name not in seen:
                    seen.add(call_name)
                    relationships.append(ParsedRelationship(
                        source=file_path,
                        target=call_name,
                        relationship=RelationshipType.CALLS,
                        file_path=file_path,
                    ))
        for child in node.children:
            _walk(child)

    _walk(root)
    return relationships


# ── Helpers ───────────────────────────────────────────────────────────────────


def _node_text(node: Node, source: bytes) -> str:
    """Get the source text for a tree-sitter node (byte-safe)."""
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _find_identifier(node: Node, source: bytes) -> str | None:
    """Find the first identifier or type_identifier in a node's children."""
    for child in node.children:
        if child.type in ("identifier", "type_identifier"):
            return _node_text(child, source)
        if child.type == "generic_type":
            return _node_text(child, source).split("<")[0]
    return None


def _extract_jsdoc(node: Node, source: bytes) -> str | None:
    """
    Extract a JSDoc comment immediately preceding a node.

    Tree-sitter places comments as siblings, so we look at the
    previous sibling for a /** ... */ comment.
    """
    prev = node.prev_named_sibling
    if prev and prev.type == "comment":
        text = _node_text(prev, source).strip()
        if text.startswith("/**"):
            # Strip the /** and */ delimiters
            text = text[3:]
            if text.endswith("*/"):
                text = text[:-2]
            # Clean up leading * on each line
            lines = []
            for line in text.split("\n"):
                line = line.strip()
                if line.startswith("*"):
                    line = line[1:].strip()
                lines.append(line)
            return "\n".join(lines).strip()
    return None


def _extract_function_sig(node: Node, source: bytes) -> str:
    """Extract the function signature (everything before the body)."""
    body = node.child_by_field_name("body")
    if body:
        sig = source[node.start_byte:body.start_byte].decode("utf-8", errors="replace").strip()
        return sig.rstrip("{").strip()
    return _node_text(node, source).split("{")[0].strip()


def _extract_arrow_sig(node: Node, source: bytes) -> str:
    """Extract arrow function parameter signature."""
    body = node.child_by_field_name("body")
    if body:
        return source[node.start_byte:body.start_byte].decode("utf-8", errors="replace").strip()
    return ""


def _extract_class_sig(node: Node, source: bytes) -> str:
    """Extract the class signature line."""
    body = node.child_by_field_name("body")
    if body:
        sig = source[node.start_byte:body.start_byte].decode("utf-8", errors="replace").strip()
        return sig.rstrip("{").strip()
    return _node_text(node, source).split("{")[0].strip()


def _extract_method_sig(node: Node, source: bytes) -> str:
    """Extract a method signature."""
    body = node.child_by_field_name("body")
    if body:
        sig = source[node.start_byte:body.start_byte].decode("utf-8", errors="replace").strip()
        return sig.rstrip("{").strip()
    return _node_text(node, source).split("{")[0].strip()
