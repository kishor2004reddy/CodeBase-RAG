"""
retrieval/hybrid_retriever.py
-----------------------------
Hybrid Retriever & Context Assembler for CodeGraphRAG.

Combines:
  1. Vector Similarity Search (Qdrant)
  2. Exact/Fuzzy Symbol Search (Neo4j)
  3. Graph Expansion (1-2 hop Cypher traversals in Neo4j)

Deduplicates and formats the retrieved chunks and relationships into a structured
prompt context ready for LLM generation.
"""

from pydantic import BaseModel, Field

from core.logging import get_logger
from retrieval.graph_expansion import GraphNodeContext, expand_graph_context
from retrieval.symbol_search import SymbolSearchResult, search_symbols
from retrieval.vector_search import VectorSearchResult, search_vectors

logger = get_logger(__name__)


class RetrievedContext(BaseModel):
    """Assembled hybrid context payload for LLM generation."""

    vector_results: list[VectorSearchResult] = Field(default_factory=list)
    symbol_results: list[SymbolSearchResult] = Field(default_factory=list)
    graph_context: list[GraphNodeContext] = Field(default_factory=list)
    formatted_context_str: str = ""
    file_citations: list[str] = Field(default_factory=list)


def retrieve_context(
    query: str,
    repo_id: str,
    top_k_vectors: int = 5,
    top_k_symbols: int = 3,
) -> RetrievedContext:
    """
    Execute hybrid retrieval (Vector + Symbol + Cypher Graph Expansion).

    Parameters
    ----------
    query : str
        User's query string.
    repo_id : str
        Scoped repository identifier.
    top_k_vectors : int
        Number of vector chunks to retrieve.
    top_k_symbols : int
        Number of exact/fuzzy symbols to retrieve.

    Returns
    -------
    RetrievedContext
        Structured retrieved context object containing formatted prompt text.
    """
    logger.info("Executing hybrid retrieval for query: '%s' (repo=%s)", query, repo_id)

    # 1. Vector Search (Qdrant)
    vector_hits = search_vectors(query=query, repo_id=repo_id, top_k=top_k_vectors)

    # 2. Symbol Search (Neo4j)
    symbol_hits = search_symbols(query=query, repo_id=repo_id, limit=top_k_symbols)

    # Extract seed file paths & symbol names for graph expansion
    seed_files = list({hit.file_path for hit in vector_hits if hit.file_path} |
                      {hit.file_path for hit in symbol_hits if hit.file_path})

    seed_symbols = list({hit.symbol_name for hit in vector_hits if hit.symbol_name} |
                        {hit.name for hit in symbol_hits if hit.name})

    # 3. Cypher Graph Expansion (Neo4j)
    graph_hits = expand_graph_context(
        seed_file_paths=seed_files,
        seed_symbol_names=seed_symbols,
        repo_id=repo_id,
        limit=12,
    )

    # 4. Format into prompt text + extract citations
    formatted_text, citations = _format_context(vector_hits, symbol_hits, graph_hits)

    return RetrievedContext(
        vector_results=vector_hits,
        symbol_results=symbol_hits,
        graph_context=graph_hits,
        formatted_context_str=formatted_text,
        file_citations=citations,
    )


def _format_context(
    vector_hits: list[VectorSearchResult],
    symbol_hits: list[SymbolSearchResult],
    graph_hits: list[GraphNodeContext],
) -> tuple[str, list[str]]:
    """Format all retrieved components into a clean, LLM-ready Markdown context string."""
    sections: list[str] = []
    citations_set: set[str] = set()

    # Section A: Directly Relevant Code Chunks (Vector Search)
    if vector_hits:
        sections.append("### 📄 Relevant Code Snippets (Vector Search)")
        for idx, vec in enumerate(vector_hits, start=1):
            cite = f"[{vec.file_path}#L{vec.start_line}-L{vec.end_line}]"
            citations_set.add(cite)
            sig_str = f" Signature: `{vec.signature}`" if vec.signature else ""
            doc_str = f"\nDocstring: {vec.docstring}" if vec.docstring else ""

            sections.append(
                f"--- Snippet {idx} ---\n"
                f"File: {vec.file_path} (Lines {vec.start_line}-{vec.end_line}){sig_str}{doc_str}\n"
                f"Symbol: {vec.symbol_type} {vec.symbol_name}\n"
                f"```\n{vec.source_code}\n```"
            )

    # Section B: Exact Symbol Definitions (Neo4j Symbol Search)
    if symbol_hits:
        sections.append("\n### 🔍 Symbol Definitions (Graph Search)")
        for sym in symbol_hits:
            cite = f"[{sym.file_path}#L{sym.start_line}-L{sym.end_line}]"
            citations_set.add(cite)
            sections.append(
                f"Symbol: {sym.symbol_type} `{sym.name}` in `{sym.file_path}` (Lines {sym.start_line}-{sym.end_line})\n"
                f"Signature: `{sym.signature or sym.name}`\n"
                f"```\n{sym.source_code}\n```"
            )

    # Section C: Knowledge Graph Dependency Structure (Cypher Expansion)
    if graph_hits:
        sections.append("\n### 🕸️ Structural Dependencies (Neo4j Graph Expansion)")
        rel_strings: list[str] = []
        for g in graph_hits:
            if g.relationship == "CALLS":
                rel_strings.append(f"- `{g.name}` CALLS `{g.target_name}`")
            elif g.relationship == "IMPORTS":
                rel_strings.append(f"- `{g.name}` IMPORTS module `{g.target_name}`")
            elif g.relationship == "INHERITS":
                rel_strings.append(f"- Class `{g.name}` INHERITS from `{g.target_name}`")
            elif g.relationship == "DEFINES":
                rel_strings.append(f"- File `{g.name}` DEFINES symbol `{g.target_name}`")

        sections.append("\n".join(rel_strings))

    return "\n\n".join(sections), sorted(list(citations_set))
