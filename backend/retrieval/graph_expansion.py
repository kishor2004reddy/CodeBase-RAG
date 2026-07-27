"""
retrieval/graph_expansion.py
----------------------------
Graph expansion engine using Neo4j and Cypher.

Takes seed files/symbols (from vector or symbol search) and executes 1-2 hop Cypher
traversals to expand context along structural graph relationships (CALLS, IMPORTS, INHERITS, DEFINES).
"""

from pydantic import BaseModel, Field

from core.config import settings
from core.logging import get_logger
from ingestion.graph_builder import get_neo4j_driver

logger = get_logger(__name__)


class GraphNodeContext(BaseModel):
    """Context node expanded from graph traversal."""

    name: str
    node_type: str  # Symbol, File, Module, Reference
    file_path: str | None = None
    relationship: str  # CALLS, IMPORTS, INHERITS, DEFINES
    direction: str  # OUTGOING, INCOMING
    target_name: str
    target_type: str
    target_file: str | None = None
    source_code: str | None = None
    docstring: str | None = None


def expand_graph_context(
    seed_file_paths: list[str],
    seed_symbol_names: list[str],
    repo_id: str,
    max_hops: int = 2,
    limit: int = 15,
) -> list[GraphNodeContext]:
    """
    Perform multi-hop graph expansion in Neo4j starting from seed entities.

    Parameters
    ----------
    seed_file_paths : list[str]
        File paths retrieved from vector/symbol search.
    seed_symbol_names : list[str]
        Symbol names retrieved from vector/symbol search.
    repo_id : str
        Scoped repository identifier.
    max_hops : int
        Max traversal depth (default 2).
    limit : int
        Maximum graph context relationships to return.

    Returns
    -------
    list[GraphNodeContext]
        Expanded graph nodes & edges representing structural dependency context.
    """
    driver = get_neo4j_driver()
    expanded: list[GraphNodeContext] = []

    if not seed_file_paths and not seed_symbol_names:
        return expanded

    with driver.session(database=settings.neo4j_database) as session:
        # 1. Expand from Seed Files (IMPORTS & DEFINES relationships)
        if seed_file_paths:
            cypher_files = """
            MATCH (f:File {repo_id: $repo_id})
            WHERE f.path IN $file_paths
            MATCH (f)-[r:IMPORTS|DEFINES]->(target)
            RETURN f.path AS source_name, "File" AS source_type, f.path AS source_file,
                   type(r) AS rel_type, "OUTGOING" AS direction,
                   COALESCE(target.name, target.path) AS target_name,
                   labels(target)[0] AS target_type,
                   target.file_path AS target_file,
                   target.source_code AS target_code,
                   target.docstring AS target_doc
            LIMIT $limit
            """
            records = session.run(
                cypher_files,
                repo_id=repo_id,
                file_paths=seed_file_paths,
                limit=limit,
            )
            for rec in records:
                expanded.append(GraphNodeContext(
                    name=rec["source_name"],
                    node_type=rec["source_type"],
                    file_path=rec["source_file"],
                    relationship=rec["rel_type"],
                    direction=rec["direction"],
                    target_name=rec["target_name"],
                    target_type=rec["target_type"],
                    target_file=rec["target_file"],
                    source_code=rec["target_code"],
                    docstring=rec["target_doc"],
                ))

        # 2. Expand from Seed Symbols (CALLS & INHERITS up to 1-2 hops)
        if seed_symbol_names and len(expanded) < limit:
            remaining = limit - len(expanded)
            cypher_symbols = """
            MATCH (s:Symbol {repo_id: $repo_id})
            WHERE s.name IN $symbol_names
            MATCH (s)-[r:CALLS|INHERITS*1..2]->(target)
            UNWIND r AS rel
            RETURN s.name AS source_name, "Symbol" AS source_type, s.file_path AS source_file,
                   type(rel) AS rel_type, "OUTGOING" AS direction,
                   COALESCE(target.name, target.path) AS target_name,
                   labels(target)[0] AS target_type,
                   target.file_path AS target_file,
                   target.source_code AS target_code,
                   target.docstring AS target_doc
            LIMIT $limit
            """
            records = session.run(
                cypher_symbols,
                repo_id=repo_id,
                symbol_names=seed_symbol_names,
                limit=remaining,
            )
            for rec in records:
                expanded.append(GraphNodeContext(
                    name=rec["source_name"],
                    node_type=rec["source_type"],
                    file_path=rec["source_file"],
                    relationship=rec["rel_type"],
                    direction=rec["direction"],
                    target_name=rec["target_name"],
                    target_type=rec["target_type"],
                    target_file=rec["target_file"],
                    source_code=rec["target_code"],
                    docstring=rec["target_doc"],
                ))

        # 3. Incoming CALLS (who calls these seed symbols?)
        if seed_symbol_names and len(expanded) < limit:
            remaining = limit - len(expanded)
            cypher_callers = """
            MATCH (caller)-[r:CALLS]->(s:Symbol {repo_id: $repo_id})
            WHERE s.name IN $symbol_names
            RETURN COALESCE(caller.name, caller.path) AS source_name,
                   labels(caller)[0] AS source_type,
                   caller.path AS source_file,
                   "CALLS" AS rel_type, "INCOMING" AS direction,
                   s.name AS target_name, "Symbol" AS target_type,
                   s.file_path AS target_file,
                   caller.source_code AS target_code,
                   caller.docstring AS target_doc
            LIMIT $limit
            """
            records = session.run(
                cypher_callers,
                repo_id=repo_id,
                symbol_names=seed_symbol_names,
                limit=remaining,
            )
            for rec in records:
                expanded.append(GraphNodeContext(
                    name=rec["source_name"],
                    node_type=rec["source_type"],
                    file_path=rec["source_file"],
                    relationship=rec["rel_type"],
                    direction=rec["direction"],
                    target_name=rec["target_name"],
                    target_type=rec["target_type"],
                    target_file=rec["target_file"],
                    source_code=rec["target_code"],
                    docstring=rec["target_doc"],
                ))

    logger.info("Graph expansion generated %d context connections", len(expanded))
    return expanded
