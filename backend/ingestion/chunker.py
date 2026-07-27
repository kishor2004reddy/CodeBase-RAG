"""
ingestion/chunker.py
--------------------
Converts parsed symbols into embeddable code chunks.

Each chunk represents a meaningful unit of code (function, class, method,
or file summary) with metadata attached. These chunks are what get
embedded and stored in the vector database for retrieval.

No arbitrary text splitting — every chunk maps to a real code construct.
"""

from pydantic import BaseModel, Field

from core.logging import get_logger
from ingestion.parser.models import (
    Language,
    ParsedFile,
    ParsedSymbol,
    SymbolType,
)

logger = get_logger(__name__)


# ── Data model ────────────────────────────────────────────────────────────────


class CodeChunk(BaseModel):
    """A single embeddable chunk of code with metadata."""

    # Identity
    chunk_id: str              # unique ID: "{repo_id}:{file_path}:{name}"
    repo_id: str               # which repo this belongs to

    # Content (what gets embedded)
    content: str               # the text sent to the embedding model
    source_code: str           # the raw code (stored for display)

    # Metadata (stored alongside the vector for filtering/display)
    file_path: str
    symbol_name: str
    symbol_type: str           # function / class / method / module
    language: str              # python / typescript
    start_line: int
    end_line: int
    docstring: str | None = None
    signature: str | None = None
    parent_class: str | None = None
    decorators: list[str] = Field(default_factory=list)


# ── Chunking logic ────────────────────────────────────────────────────────────


def chunk_parsed_file(parsed_file: ParsedFile, repo_id: str) -> list[CodeChunk]:
    """
    Convert a ParsedFile into a list of CodeChunks ready for embedding.

    Creates:
      1. One chunk per symbol (function, class, method, interface)
      2. One file-summary chunk that gives an overview of the file

    Parameters
    ----------
    parsed_file : ParsedFile
        The AST-parsed result for a single file.
    repo_id : str
        Unique identifier for the repository.

    Returns
    -------
    list[CodeChunk]
        All chunks for this file.
    """
    chunks: list[CodeChunk] = []

    # ── Symbol-level chunks ───────────────────────────────────────────
    for symbol in parsed_file.symbols:
        chunk = _symbol_to_chunk(symbol, repo_id)
        chunks.append(chunk)

    # ── File-summary chunk ────────────────────────────────────────────
    if parsed_file.symbols:
        summary_chunk = _make_file_summary(parsed_file, repo_id)
        chunks.append(summary_chunk)

    logger.debug(
        "Chunked %s: %d chunks (%d symbols + 1 summary)",
        parsed_file.file_path, len(chunks), len(parsed_file.symbols),
    )
    return chunks


def _symbol_to_chunk(symbol: ParsedSymbol, repo_id: str) -> CodeChunk:
    """
    Convert a single parsed symbol into an embeddable chunk.

    The 'content' field is a structured text representation designed to
    give the embedding model rich semantic context:
      - File path and language
      - Symbol type and name
      - Signature
      - Docstring (if present)
      - Source code
    """
    # Build a rich text representation for the embedding model
    parts: list[str] = []

    # Header: what is this?
    kind = symbol.symbol_type.value
    if symbol.parent_class:
        parts.append(f"[{kind}] {symbol.parent_class}.{symbol.name}")
    else:
        parts.append(f"[{kind}] {symbol.name}")

    parts.append(f"File: {symbol.file_path}")
    parts.append(f"Language: {symbol.language.value}")

    # Signature
    if symbol.signature:
        parts.append(f"Signature: {symbol.signature}")

    # Decorators
    if symbol.decorators:
        parts.append(f"Decorators: {', '.join(symbol.decorators)}")

    # Docstring — important semantic signal
    if symbol.docstring:
        parts.append(f"Documentation: {symbol.docstring}")

    # Source code
    parts.append(f"Source code:\n{symbol.source_code}")

    content = "\n".join(parts)

    # Build unique ID
    name_key = symbol.name
    if symbol.parent_class:
        name_key = f"{symbol.parent_class}.{symbol.name}"

    chunk_id = f"{repo_id}:{symbol.file_path}:{name_key}"

    return CodeChunk(
        chunk_id=chunk_id,
        repo_id=repo_id,
        content=content,
        source_code=symbol.source_code,
        file_path=symbol.file_path,
        symbol_name=symbol.name,
        symbol_type=symbol.symbol_type.value,
        language=symbol.language.value,
        start_line=symbol.start_line,
        end_line=symbol.end_line,
        docstring=symbol.docstring,
        signature=symbol.signature,
        parent_class=symbol.parent_class,
        decorators=symbol.decorators,
    )


def _make_file_summary(parsed_file: ParsedFile, repo_id: str) -> CodeChunk:
    """
    Create a file-level summary chunk.

    This gives the embedding model an overview of what the file contains,
    so queries like "where is authentication handled?" can match the
    right file even if no single function name matches.
    """
    parts: list[str] = []
    parts.append(f"[module] {parsed_file.file_path}")
    parts.append(f"Language: {parsed_file.language.value}")
    parts.append(f"Lines of code: {parsed_file.lines_of_code}")

    # List all symbols defined in this file
    functions = [s for s in parsed_file.symbols if s.symbol_type == SymbolType.FUNCTION]
    classes = [s for s in parsed_file.symbols if s.symbol_type == SymbolType.CLASS]
    methods = [s for s in parsed_file.symbols if s.symbol_type == SymbolType.METHOD]
    interfaces = [s for s in parsed_file.symbols if s.symbol_type == SymbolType.INTERFACE]

    if classes:
        parts.append(f"Classes: {', '.join(c.name for c in classes)}")
    if interfaces:
        parts.append(f"Interfaces: {', '.join(i.name for i in interfaces)}")
    if functions:
        parts.append(f"Functions: {', '.join(f.name for f in functions)}")
    if methods:
        method_descs = []
        for m in methods:
            if m.parent_class:
                method_descs.append(f"{m.parent_class}.{m.name}")
            else:
                method_descs.append(m.name)
        parts.append(f"Methods: {', '.join(method_descs)}")

    # Include docstrings from top-level symbols for richer context
    for sym in parsed_file.symbols:
        if sym.docstring and sym.symbol_type in (SymbolType.FUNCTION, SymbolType.CLASS):
            parts.append(f"{sym.name}: {sym.docstring[:200]}")

    content = "\n".join(parts)

    return CodeChunk(
        chunk_id=f"{repo_id}:{parsed_file.file_path}:__module__",
        repo_id=repo_id,
        content=content,
        source_code="",  # file summary has no single source block
        file_path=parsed_file.file_path,
        symbol_name="__module__",
        symbol_type="module",
        language=parsed_file.language.value,
        start_line=1,
        end_line=parsed_file.lines_of_code,
    )
