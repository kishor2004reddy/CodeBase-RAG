"""
ingestion/storage.py
--------------------
Manages Qdrant vector database storage for code embeddings.

Handles:
  - Collection creation with proper vector config
  - Upserting chunk embeddings with metadata payloads
  - Deleting repo data for re-ingestion
"""

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    Filter,
    FieldCondition,
    MatchValue,
    PointStruct,
    VectorParams,
)

from core.config import settings
from core.logging import get_logger
from ingestion.chunker import CodeChunk

logger = get_logger(__name__)

# ── Client singleton ─────────────────────────────────────────────────────────

_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    """Return the singleton Qdrant client."""
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.qdrant_url, timeout=60)
        logger.info("Qdrant client created for %s", settings.qdrant_url)
    return _client


# ── Collection management ────────────────────────────────────────────────────


def ensure_collection(vector_size: int) -> None:
    """
    Create the Qdrant collection if it doesn't exist.

    Parameters
    ----------
    vector_size : int
        Dimension of the embedding vectors (e.g. 384 for bge-small).
    """
    client = _get_client()
    collection_name = settings.qdrant_collection

    # Check if collection already exists
    existing = [c.name for c in client.get_collections().collections]
    if collection_name in existing:
        logger.info("Qdrant collection '%s' already exists", collection_name)
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=vector_size,
            distance=Distance.COSINE,
        ),
    )
    logger.info(
        "Created Qdrant collection '%s' (dim=%d, distance=cosine)",
        collection_name, vector_size,
    )


# ── Upsert embeddings ────────────────────────────────────────────────────────


def upsert_chunks(
    chunks: list[CodeChunk],
    embeddings: list[list[float]],
) -> None:
    """
    Store chunk embeddings + metadata in Qdrant.

    Each point's ID is derived from the chunk_id (deterministic hash)
    so re-ingesting the same chunk updates rather than duplicates.

    Parameters
    ----------
    chunks : list[CodeChunk]
        The code chunks with metadata.
    embeddings : list[list[float]]
        Corresponding embedding vectors (same order as chunks).
    """
    if not chunks:
        return

    client = _get_client()
    collection_name = settings.qdrant_collection

    points: list[PointStruct] = []
    for chunk, vector in zip(chunks, embeddings):
        # Use a deterministic hash of chunk_id as the point ID
        point_id = _deterministic_id(chunk.chunk_id)

        # Build the metadata payload (stored alongside the vector)
        payload = {
            "chunk_id": chunk.chunk_id,
            "repo_id": chunk.repo_id,
            "content": chunk.content,
            "source_code": chunk.source_code,
            "file_path": chunk.file_path,
            "symbol_name": chunk.symbol_name,
            "symbol_type": chunk.symbol_type,
            "language": chunk.language,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "docstring": chunk.docstring or "",
            "signature": chunk.signature or "",
            "parent_class": chunk.parent_class or "",
            "decorators": chunk.decorators,
        }

        points.append(PointStruct(
            id=point_id,
            vector=vector,
            payload=payload,
        ))

    # Upsert in batches of 100
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        client.upsert(
            collection_name=collection_name,
            points=batch,
        )

    logger.info(
        "Upserted %d vectors to Qdrant collection '%s'",
        len(points), collection_name,
    )


# ── Cleanup ──────────────────────────────────────────────────────────────────


def delete_repo_vectors(repo_id: str) -> None:
    """
    Delete all vectors belonging to a repo (for re-ingestion).

    Parameters
    ----------
    repo_id : str
        The repository identifier to delete vectors for.
    """
    client = _get_client()
    collection_name = settings.qdrant_collection

    # Check if collection exists first
    existing = [c.name for c in client.get_collections().collections]
    if collection_name not in existing:
        return

    client.delete(
        collection_name=collection_name,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="repo_id",
                    match=MatchValue(value=repo_id),
                ),
            ],
        ),
    )
    logger.info("Deleted vectors for repo %s from Qdrant", repo_id)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _deterministic_id(text: str) -> int:
    """
    Generate a deterministic positive integer ID from a string.

    Uses a hash to ensure the same chunk_id always maps to the same
    point ID — so re-ingestion updates existing points.
    """
    import hashlib
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    # Take first 15 hex chars → fits in a 64-bit positive integer
    return int(h[:15], 16)
