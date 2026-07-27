"""
ingestion/parser/python_parser.py
---------------------------------
Parses Python source files using tree-sitter to extract:
  - Functions (name, args, docstring, decorators, source code)
  - Classes (name, bases, docstring, decorators)
  - Methods (functions inside classes — linked to their parent)
  - Import relationships (import X / from X import Y)
  - Call relationships (function A calls function B)
  - Inheritance relationships (class A(B))

Returns a ParsedFile containing all symbols and relationships.
"""

import tree_sitter_python as tspython
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

PY_LANGUAGE = Language(tspython.language())


def _make_parser() -> Parser:
    """Create a fresh tree-sitter parser for Python."""
    parser = Parser(PY_LANGUAGE)
    return parser


# ── Public API ────────────────────────────────────────────────────────────────


def parse_python_file(source_code: str, file_path: str) -> ParsedFile:
    """
    Parse a single Python file and extract all symbols + relationships.

    Parameters
    ----------
    source_code : str
        The raw file contents.
    file_path : str
        Relative path within the repo (used for labelling, not reading).

    Returns
    -------
    ParsedFile
        All symbols and relationships found in this file.
    """
    source_bytes = source_code.encode("utf-8")
    parser = _make_parser()
    tree = parser.parse(source_bytes)
    root = tree.root_node

    symbols: list[ParsedSymbol] = []
    relationships: list[ParsedRelationship] = []

    # Walk top-level children of the module
    for child in root.children:
        node_type = child.type

        # ── Top-level functions ───────────────────────────────────────
        if node_type == "function_definition":
            sym = _extract_function(child, source_bytes, file_path, parent_class=None)
            if sym:
                symbols.append(sym)
                # The file DEFINES this function
                relationships.append(ParsedRelationship(
                    source=file_path,
                    target=sym.name,
                    relationship=RelationshipType.DEFINES,
                    file_path=file_path,
                ))

        # ── Decorated definitions (wraps a function or class) ─────────
        elif node_type == "decorated_definition":
            inner = _get_decorated_inner(child)
            if inner and inner.type == "function_definition":
                sym = _extract_function(inner, source_bytes, file_path, parent_class=None, decorator_node=child)
                if sym:
                    symbols.append(sym)
                    relationships.append(ParsedRelationship(
                        source=file_path,
                        target=sym.name,
                        relationship=RelationshipType.DEFINES,
                        file_path=file_path,
                    ))
            elif inner and inner.type == "class_definition":
                class_syms, class_rels = _extract_class(inner, source_bytes, file_path, decorator_node=child)
                symbols.extend(class_syms)
                relationships.extend(class_rels)

        # ── Classes ───────────────────────────────────────────────────
        elif node_type == "class_definition":
            class_syms, class_rels = _extract_class(child, source_bytes, file_path)
            symbols.extend(class_syms)
            relationships.extend(class_rels)

        # ── Imports ───────────────────────────────────────────────────
        elif node_type in ("import_statement", "import_from_statement"):
            rels = _extract_import(child, source_bytes, file_path)
            relationships.extend(rels)

    # ── Extract function calls from the entire file ───────────────────
    call_rels = _extract_calls(root, source_bytes, file_path)
    relationships.extend(call_rels)

    loc = source_code.count("\n") + (1 if source_code and not source_code.endswith("\n") else 0)

    logger.debug(
        "Parsed %s: %d symbols, %d relationships, %d LOC",
        file_path, len(symbols), len(relationships), loc,
    )

    return ParsedFile(
        file_path=file_path,
        language=LangEnum.PYTHON,
        symbols=symbols,
        relationships=relationships,
        lines_of_code=loc,
    )


# ── Function extraction ──────────────────────────────────────────────────────


def _extract_function(
    node: Node,
    source: bytes,
    file_path: str,
    parent_class: str | None,
    decorator_node: Node | None = None,
) -> ParsedSymbol | None:
    """Extract a function/method definition from a tree-sitter node."""

    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None

    name = _node_text(name_node, source)

    # Determine symbol type
    sym_type = SymbolType.METHOD if parent_class else SymbolType.FUNCTION

    # Get the full source — if decorated, include the decorators
    src_node = decorator_node if decorator_node else node
    source_code = _node_text(src_node, source)

    # Signature: the first line of the function (def foo(args):)
    sig = _extract_signature(node, source)

    # Docstring: first expression_statement > string in the body
    docstring = _extract_docstring(node, source)

    # Decorators
    decorators = _extract_decorators(decorator_node, source) if decorator_node else _extract_decorators(node, source)

    return ParsedSymbol(
        name=name,
        symbol_type=sym_type,
        language=LangEnum.PYTHON,
        file_path=file_path,
        start_line=src_node.start_point[0] + 1,  # tree-sitter is 0-indexed
        end_line=src_node.end_point[0] + 1,
        source_code=source_code,
        docstring=docstring,
        decorators=decorators,
        parent_class=parent_class,
        signature=sig,
    )


# ── Class extraction ─────────────────────────────────────────────────────────


def _extract_class(
    node: Node,
    source: bytes,
    file_path: str,
    decorator_node: Node | None = None,
) -> tuple[list[ParsedSymbol], list[ParsedRelationship]]:
    """Extract a class definition — its body methods, and inheritance."""

    symbols: list[ParsedSymbol] = []
    relationships: list[ParsedRelationship] = []

    name_node = node.child_by_field_name("name")
    if name_node is None:
        return symbols, relationships

    class_name = _node_text(name_node, source)

    # The class symbol itself
    src_node = decorator_node if decorator_node else node
    docstring = _extract_docstring(node, source)
    decorators = _extract_decorators(decorator_node, source) if decorator_node else _extract_decorators(node, source)

    class_sym = ParsedSymbol(
        name=class_name,
        symbol_type=SymbolType.CLASS,
        language=LangEnum.PYTHON,
        file_path=file_path,
        start_line=src_node.start_point[0] + 1,
        end_line=src_node.end_point[0] + 1,
        source_code=_node_text(src_node, source),
        docstring=docstring,
        decorators=decorators,
        signature=_extract_class_signature(node, source),
    )
    symbols.append(class_sym)

    # File DEFINES this class
    relationships.append(ParsedRelationship(
        source=file_path,
        target=class_name,
        relationship=RelationshipType.DEFINES,
        file_path=file_path,
    ))

    # ── Superclasses → INHERITS edges ────────────────────────────────
    superclasses = node.child_by_field_name("superclasses")
    if superclasses:
        for arg in superclasses.children:
            if arg.type in ("identifier", "attribute"):
                base_name = _node_text(arg, source)
                relationships.append(ParsedRelationship(
                    source=class_name,
                    target=base_name,
                    relationship=RelationshipType.INHERITS,
                    file_path=file_path,
                ))

    # ── Methods inside the class body ────────────────────────────────
    body = node.child_by_field_name("body")
    if body:
        for child in body.children:
            if child.type == "function_definition":
                method_sym = _extract_function(child, source, file_path, parent_class=class_name)
                if method_sym:
                    symbols.append(method_sym)
            elif child.type == "decorated_definition":
                inner = _get_decorated_inner(child)
                if inner and inner.type == "function_definition":
                    method_sym = _extract_function(
                        inner, source, file_path,
                        parent_class=class_name, decorator_node=child,
                    )
                    if method_sym:
                        symbols.append(method_sym)

    return symbols, relationships


# ── Import extraction ─────────────────────────────────────────────────────────


def _extract_import(node: Node, source: bytes, file_path: str) -> list[ParsedRelationship]:
    """Extract import relationships from import / from-import statements."""
    relationships: list[ParsedRelationship] = []

    if node.type == "import_statement":
        # import foo, bar, baz
        for child in node.children:
            if child.type in ("dotted_name", "aliased_import"):
                module_name = _node_text(child, source).split(" as ")[0].strip()
                relationships.append(ParsedRelationship(
                    source=file_path,
                    target=module_name,
                    relationship=RelationshipType.IMPORTS,
                    file_path=file_path,
                ))

    elif node.type == "import_from_statement":
        # from foo.bar import baz
        module_node = node.child_by_field_name("module_name")
        if module_node:
            module_name = _node_text(module_node, source)
            relationships.append(ParsedRelationship(
                source=file_path,
                target=module_name,
                relationship=RelationshipType.IMPORTS,
                file_path=file_path,
            ))

    return relationships


# ── Call extraction ───────────────────────────────────────────────────────────


def _extract_calls(root: Node, source: bytes, file_path: str) -> list[ParsedRelationship]:
    """Walk the entire AST and find function/method calls."""
    relationships: list[ParsedRelationship] = []
    seen: set[str] = set()  # deduplicate

    def _walk(node: Node) -> None:
        if node.type == "call":
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


def _extract_signature(func_node: Node, source: bytes) -> str:
    """Extract the 'def foo(x, y) -> int:' line."""
    # The signature is everything up to the colon on the def line
    start_b = func_node.start_byte
    body = func_node.child_by_field_name("body")
    if body:
        end_b = body.start_byte
    else:
        end_b = func_node.end_byte

    sig = source[start_b:end_b].decode("utf-8", errors="replace").strip()
    # Remove trailing colon
    if sig.endswith(":"):
        sig = sig[:-1].strip()
    return sig


def _extract_class_signature(class_node: Node, source: bytes) -> str:
    """Extract the 'class Foo(Bar, Baz):' line."""
    start_b = class_node.start_byte
    body = class_node.child_by_field_name("body")
    if body:
        end_b = body.start_byte
    else:
        end_b = class_node.end_byte
    sig = source[start_b:end_b].decode("utf-8", errors="replace").strip()
    if sig.endswith(":"):
        sig = sig[:-1].strip()
    return sig


def _extract_docstring(node: Node, source: bytes) -> str | None:
    """
    Extract the docstring from a function or class node.

    In Python AST, a docstring is the first child of the body that is
    an expression_statement containing a string literal.
    """
    body = node.child_by_field_name("body")
    if not body or not body.children:
        return None

    first = body.children[0]
    if first.type == "expression_statement":
        for child in first.children:
            if child.type == "string":
                raw = _node_text(child, source)
                # Strip triple quotes
                for quote in ('"""', "'''", '"', "'"):
                    if raw.startswith(quote) and raw.endswith(quote):
                        return raw[len(quote):-len(quote)].strip()
                return raw
    return None


def _extract_decorators(node: Node | None, source: bytes) -> list[str]:
    """Extract decorator names from a decorated_definition or function node."""
    if node is None:
        return []

    decorators: list[str] = []
    for child in node.children:
        if child.type == "decorator":
            dec_text = _node_text(child, source).lstrip("@").strip()
            decorators.append(dec_text)
    return decorators


def _get_decorated_inner(decorated_node: Node) -> Node | None:
    """Get the actual function/class definition inside a decorated_definition."""
    for child in decorated_node.children:
        if child.type in ("function_definition", "class_definition"):
            return child
    return None
