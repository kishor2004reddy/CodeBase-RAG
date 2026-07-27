"""
retrieval/vector_search.py
--------------------------
Performs semantic vector search against Qdrant collection.

Embeds user queries into the vector space and retrieves top-K nearest code chunks
scoped by repo_id.
"""

from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from core.config import settings
from core.logging import get_logger
from ingestion.embedder import embed_query

logger = get_logger(__name__)

_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    """Singleton Qdrant client."""
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.qdrant_url)
    return _client


class VectorSearchResult(BaseModel):
    """A single code chunk retrieved via vector similarity search."""

    chunk_id: str
    repo_id: str
    file_path: str
    symbol_name: str
    symbol_type: str
    language: str
    start_line: int
    end_line: int
    content: str
    source_code: str
    docstring: str | None = None
    signature: str | None = None
    score: float


def search_vectors(
    query: str,
    repo_id: str,
    top_k: int = 5,
) -> list[VectorSearchResult]:
    """
    Search Qdrant for code chunks semantically relevant to query.

    Parameters
    ----------
    query : str
        User's natural language question.
    repo_id : str
        Scoped repository identifier.
    top_k : int
        Number of nearest neighbors to retrieve.

    Returns
    -------
    list[VectorSearchResult]
        Ranked list of vector search results.
    """
    client = _get_client()
    query_vector = embed_query(query)

    # Scoped filter by repo_id
    query_filter = Filter(
        must=[
            FieldCondition(
                key="repo_id",
                match=MatchValue(value=repo_id),
            ),
        ]
    )

    try:
        # Perform query in Qdrant
        hits = client.query_points(
            collection_name=settings.qdrant_collection,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
        ).points

        results: list[VectorSearchResult] = []
        for hit in hits:
            payload = hit.payload or {}
            results.append(VectorSearchResult(
                chunk_id=payload.get("chunk_id", str(hit.id)),
                repo_id=payload.get("repo_id", repo_id),
                file_path=payload.get("file_path", ""),
                symbol_name=payload.get("symbol_name", ""),
                symbol_type=payload.get("symbol_type", "unknown"),
                language=payload.get("language", "unknown"),
                start_line=payload.get("start_line", 1),
                end_line=payload.get("end_line", 1),
                content=payload.get("content", ""),
                source_code=payload.get("source_code", ""),
                docstring=payload.get("docstring") or None,
                signature=payload.get("signature") or None,
                score=float(hit.score),
            ))

        logger.info(
            "Vector search for query '%s' returned %d results",
            query, len(results),
        )
        return results

    except Exception as e:
        logger.error("Vector search failed: %s", e)
        return []
