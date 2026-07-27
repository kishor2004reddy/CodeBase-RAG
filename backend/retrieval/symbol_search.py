"""
retrieval/symbol_search.py
--------------------------
Searches Neo4j for matching symbol definitions by name.

Used as part of hybrid retrieval to instantly locate symbols when the query
contains exact or fuzzy code identifiers (e.g., "UserService", "authenticate", "parse_file").
"""

from pydantic import BaseModel, Field

from core.config import settings
from core.logging import get_logger
from ingestion.graph_builder import get_neo4j_driver

logger = get_logger(__name__)


class SymbolSearchResult(BaseModel):
    """A symbol node found via exact/fuzzy name search."""

    name: str
    symbol_type: str
    file_path: str
    start_line: int
    end_line: int
    signature: str | None = None
    docstring: str | None = None
    source_code: str
    score: float = 1.0  # Exact match gets 1.0, fuzzy match gets lower


def search_symbols(
    query: str,
    repo_id: str,
    limit: int = 5,
) -> list[SymbolSearchResult]:
    """
    Search Neo4j for symbols matching tokens in the query string.

    Parameters
    ----------
    query : str
        User search query (e.g., "Where is UserService defined?").
    repo_id : str
        Scoped repository ID.
    limit : int
        Max results to return.

    Returns
    -------
    list[SymbolSearchResult]
        Matching symbol nodes found in the knowledge graph.
    """
    driver = get_neo4j_driver()
    results: list[SymbolSearchResult] = []

    # Extract potential symbol tokens from query (alphanumeric + underscores)
    import re
    tokens = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", query)

    if not tokens:
        return results

    with driver.session(database=settings.neo4j_database) as session:
        # 1. Exact match query
        cypher_exact = """
        MATCH (s:Symbol {repo_id: $repo_id})
        WHERE s.name IN $tokens
        RETURN s.name AS name, s.symbol_type AS symbol_type, s.file_path AS file_path,
               s.start_line AS start_line, s.end_line AS end_line,
               s.signature AS signature, s.docstring AS docstring, s.source_code AS source_code
        LIMIT $limit
        """
        records = session.run(cypher_exact, repo_id=repo_id, tokens=tokens, limit=limit)
        for r in records:
            results.append(SymbolSearchResult(
                name=r["name"],
                symbol_type=r["symbol_type"],
                file_path=r["file_path"],
                start_line=r["start_line"] or 1,
                end_line=r["end_line"] or 1,
                signature=r["signature"],
                docstring=r["docstring"],
                source_code=r["source_code"] or "",
                score=1.0,
            ))

        # 2. Fuzzy substring match if we have space left
        if len(results) < limit:
            remaining = limit - len(results)
            existing_names = {res.name for res in results}

            cypher_fuzzy = """
            MATCH (s:Symbol {repo_id: $repo_id})
            WHERE ANY(token IN $tokens WHERE toLower(s.name) CONTAINS toLower(token))
              AND NOT s.name IN $existing
            RETURN s.name AS name, s.symbol_type AS symbol_type, s.file_path AS file_path,
                   s.start_line AS start_line, s.end_line AS end_line,
                   s.signature AS signature, s.docstring AS docstring, s.source_code AS source_code
            LIMIT $limit
            """
            fuzzy_records = session.run(
                cypher_fuzzy,
                repo_id=repo_id,
                tokens=tokens,
                existing=list(existing_names),
                limit=remaining,
            )
            for r in fuzzy_records:
                results.append(SymbolSearchResult(
                    name=r["name"],
                    symbol_type=r["symbol_type"],
                    file_path=r["file_path"],
                    start_line=r["start_line"] or 1,
                    end_line=r["end_line"] or 1,
                    signature=r["signature"],
                    docstring=r["docstring"],
                    source_code=r["source_code"] or "",
                    score=0.8,
                ))

    logger.info("Symbol search for query '%s' returned %d matches", query, len(results))
    return results
