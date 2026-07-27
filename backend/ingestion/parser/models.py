"""
ingestion/parser/models.py
--------------------------
Shared data models for AST-parsed code symbols and relationships.

Every parser (Python, TypeScript) outputs these same types so the rest of
the pipeline (chunker, graph builder, embedder) doesn't need to know which
language it's dealing with.
"""

from enum import Enum

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────


class Language(str, Enum):
    """Programming languages we support."""

    PYTHON = "python"
    TYPESCRIPT = "typescript"


class SymbolType(str, Enum):
    """The kind of code symbol extracted from an AST."""

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    INTERFACE = "interface"      # TypeScript-only
    VARIABLE = "variable"        # top-level assignments / const exports
    MODULE = "module"            # file-level summary node


class RelationshipType(str, Enum):
    """Edge types for the knowledge graph."""

    IMPORTS = "IMPORTS"          # file/module A imports module B
    CALLS = "CALLS"              # function A calls function B
    INHERITS = "INHERITS"        # class A extends/inherits class B
    DEFINES = "DEFINES"          # file defines symbol
    EXPORTS = "EXPORTS"          # file exports symbol (TS)


# ── Data models ───────────────────────────────────────────────────────────────


class ParsedSymbol(BaseModel):
    """One extracted symbol (function, class, method, etc.)."""

    name: str
    symbol_type: SymbolType
    language: Language

    # Location in the original file
    file_path: str                       # relative path within the repo
    start_line: int
    end_line: int

    # Source code
    source_code: str                     # the raw text of this symbol
    docstring: str | None = None         # extracted docstring, if any

    # Extra metadata
    decorators: list[str] = Field(default_factory=list)   # @app.get, etc.
    parent_class: str | None = None      # set if this is a METHOD inside a class
    signature: str | None = None         # function/method signature line


class ParsedRelationship(BaseModel):
    """One edge in the knowledge graph."""

    source: str          # e.g. "auth/service.py" or "UserService"
    target: str          # e.g. "database" or "BaseService"
    relationship: RelationshipType
    file_path: str       # file where this relationship was found


class ParsedFile(BaseModel):
    """Complete parse result for a single source file."""

    file_path: str                   # relative path in the repo
    language: Language
    symbols: list[ParsedSymbol] = Field(default_factory=list)
    relationships: list[ParsedRelationship] = Field(default_factory=list)
    lines_of_code: int = 0           # total LOC (for stats)
