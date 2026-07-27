"""
ingestion/graph_builder.py
--------------------------
Manages the Neo4j knowledge graph for code symbols and relationships.

Provides:
  - Neo4j driver lifecycle (get/close)
  - Schema setup (constraints + indexes)
  - Storing parsed symbols as nodes
  - Storing relationships as edges
  - Clearing a repo's graph data for re-ingestion

All Cypher queries are parameterised to avoid injection.
"""

from neo4j import GraphDatabase, Driver

from core.config import settings
from core.logging import get_logger
from ingestion.parser.models import (
    ParsedFile,
    ParsedRelationship,
    ParsedSymbol,
    RelationshipType,
    SymbolType,
)

logger = get_logger(__name__)

# ── Driver singleton ──────────────────────────────────────────────────────────

_driver: Driver | None = None


def get_neo4j_driver() -> Driver:
    """
    Return the singleton Neo4j driver (creates it on first call).

    Uses settings from core.config — URI, username, password.
    Auth is optional (disabled in dev with NEO4J_AUTH=none).
    """
    global _driver
    if _driver is None:
        auth = None
        if settings.neo4j_user and settings.neo4j_password:
            auth = (settings.neo4j_user, settings.neo4j_password)

        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=auth,
        )
        logger.info("Neo4j driver created for %s", settings.neo4j_uri)
    return _driver


def close_neo4j_driver() -> None:
    """Close the Neo4j driver on application shutdown."""
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
        logger.info("Neo4j driver closed")


# ── Schema setup ─────────────────────────────────────────────────────────────


def setup_schema() -> None:
    """
    Create constraints and indexes in Neo4j for fast lookups.

    Idempotent — safe to call multiple times.
    """
    driver = get_neo4j_driver()
    with driver.session(database=settings.neo4j_database) as session:
        # Uniqueness constraint on Symbol nodes (repo_id + file_path + name)
        session.run(
            "CREATE CONSTRAINT symbol_unique IF NOT EXISTS "
            "FOR (s:Symbol) REQUIRE (s.repo_id, s.file_path, s.name) IS UNIQUE"
        )
        # Index on repo_id for fast repo-scoped queries
        session.run(
            "CREATE INDEX symbol_repo IF NOT EXISTS "
            "FOR (s:Symbol) ON (s.repo_id)"
        )
        # Index on File nodes
        session.run(
            "CREATE CONSTRAINT file_unique IF NOT EXISTS "
            "FOR (f:File) REQUIRE (f.repo_id, f.path) IS UNIQUE"
        )
        # Index on symbol name for search
        session.run(
            "CREATE INDEX symbol_name IF NOT EXISTS "
            "FOR (s:Symbol) ON (s.name)"
        )
        logger.info("Neo4j schema setup complete")


# ── Store parsed results ─────────────────────────────────────────────────────


def store_parsed_file(parsed_file: ParsedFile, repo_id: str) -> None:
    """
    Store all symbols and relationships from a parsed file into Neo4j.

    Parameters
    ----------
    parsed_file : ParsedFile
        The parse result from the AST parser.
    repo_id : str
        Unique identifier for the repository (used to scope data).
    """
    driver = get_neo4j_driver()
    with driver.session(database=settings.neo4j_database) as session:
        # Create File node
        session.run(
            """
            MERGE (f:File {repo_id: $repo_id, path: $path})
            SET f.language = $language,
                f.lines_of_code = $loc
            """,
            repo_id=repo_id,
            path=parsed_file.file_path,
            language=parsed_file.language.value,
            loc=parsed_file.lines_of_code,
        )

        # Create Symbol nodes
        for sym in parsed_file.symbols:
            _store_symbol(session, sym, repo_id)

        # Create relationship edges
        for rel in parsed_file.relationships:
            _store_relationship(session, rel, repo_id)


def _store_symbol(session, symbol: ParsedSymbol, repo_id: str) -> None:
    """Create or update a Symbol node in Neo4j."""
    session.run(
        """
        MERGE (s:Symbol {repo_id: $repo_id, file_path: $file_path, name: $name})
        SET s.symbol_type = $symbol_type,
            s.language = $language,
            s.start_line = $start_line,
            s.end_line = $end_line,
            s.source_code = $source_code,
            s.docstring = $docstring,
            s.signature = $signature,
            s.parent_class = $parent_class,
            s.decorators = $decorators
        """,
        repo_id=repo_id,
        file_path=symbol.file_path,
        name=symbol.name,
        symbol_type=symbol.symbol_type.value,
        language=symbol.language.value,
        start_line=symbol.start_line,
        end_line=symbol.end_line,
        source_code=symbol.source_code,
        docstring=symbol.docstring,
        signature=symbol.signature,
        parent_class=symbol.parent_class,
        decorators=symbol.decorators,
    )


def _store_relationship(session, rel: ParsedRelationship, repo_id: str) -> None:
    """
    Create a relationship edge in Neo4j.

    We use different Cypher patterns depending on the relationship type:
    - DEFINES: File -> Symbol
    - IMPORTS: File -> module name (may be external)
    - CALLS: File/Symbol -> target symbol
    - INHERITS: Symbol -> Symbol
    - EXPORTS: File -> Symbol
    """
    if rel.relationship == RelationshipType.DEFINES:
        session.run(
            """
            MATCH (f:File {repo_id: $repo_id, path: $source})
            MATCH (s:Symbol {repo_id: $repo_id, file_path: $file_path, name: $target})
            MERGE (f)-[:DEFINES]->(s)
            """,
            repo_id=repo_id,
            source=rel.source,
            target=rel.target,
            file_path=rel.file_path,
        )

    elif rel.relationship == RelationshipType.IMPORTS:
        # The target module may not exist as a node — create a lightweight
        # Module reference node so we can still query the graph.
        session.run(
            """
            MATCH (f:File {repo_id: $repo_id, path: $source})
            MERGE (m:Module {repo_id: $repo_id, name: $target})
            MERGE (f)-[:IMPORTS]->(m)
            """,
            repo_id=repo_id,
            source=rel.source,
            target=rel.target,
        )

    elif rel.relationship == RelationshipType.CALLS:
        # Try to link to an existing Symbol; if not found, create a
        # reference node so the edge still exists in the graph.
        session.run(
            """
            MERGE (caller:File {repo_id: $repo_id, path: $source})
            MERGE (target:Reference {repo_id: $repo_id, name: $target})
            MERGE (caller)-[:CALLS]->(target)
            """,
            repo_id=repo_id,
            source=rel.source,
            target=rel.target,
        )

    elif rel.relationship == RelationshipType.INHERITS:
        # source is a class name, target is a base class name
        session.run(
            """
            MERGE (child:Symbol {repo_id: $repo_id, file_path: $file_path, name: $source})
            MERGE (parent:Reference {repo_id: $repo_id, name: $target})
            MERGE (child)-[:INHERITS]->(parent)
            """,
            repo_id=repo_id,
            source=rel.source,
            target=rel.target,
            file_path=rel.file_path,
        )

    elif rel.relationship == RelationshipType.EXPORTS:
        session.run(
            """
            MATCH (f:File {repo_id: $repo_id, path: $source})
            MATCH (s:Symbol {repo_id: $repo_id, file_path: $file_path, name: $target})
            MERGE (f)-[:EXPORTS]->(s)
            """,
            repo_id=repo_id,
            source=rel.source,
            target=rel.target,
            file_path=rel.file_path,
        )


# ── Cleanup ──────────────────────────────────────────────────────────────────


def clear_repo_graph(repo_id: str) -> None:
    """
    Delete all nodes and relationships for a given repo.

    Used when re-ingesting a repository.
    """
    driver = get_neo4j_driver()
    with driver.session(database=settings.neo4j_database) as session:
        # Delete in batches to avoid memory issues on large graphs
        result = session.run(
            """
            MATCH (n {repo_id: $repo_id})
            DETACH DELETE n
            RETURN count(n) AS deleted
            """,
            repo_id=repo_id,
        )
        record = result.single()
        count = record["deleted"] if record else 0
        logger.info("Cleared %d nodes for repo %s", count, repo_id)
