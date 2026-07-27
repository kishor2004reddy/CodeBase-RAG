"""
ingestion/embedder.py
---------------------
Generates vector embeddings for code chunks using sentence-transformers.

Uses BAAI/bge-small-en-v1.5 by default — a compact, high-quality model
that runs fast even on CPU. The model is loaded once (singleton) and
reused for all embedding requests.

Outputs 384-dimensional vectors suitable for Qdrant storage.
"""

from sentence_transformers import SentenceTransformer

from core.config import settings
from core.logging import get_logger
from ingestion.chunker import CodeChunk

logger = get_logger(__name__)

# ── Model singleton ──────────────────────────────────────────────────────────

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """Load the embedding model (once, lazily)."""
    global _model
    if _model is None:
        logger.info("Loading embedding model: %s", settings.embedding_model)
        _model = SentenceTransformer(settings.embedding_model)
        dim = get_embedding_dimension()
        logger.info("Embedding model loaded (dim=%d)", dim)
    return _model


def get_embedding_dimension() -> int:
    """Return the vector dimension of the loaded model."""
    model = _get_model()
    if hasattr(model, "get_embedding_dimension"):
        return model.get_embedding_dimension()
    return model.get_sentence_embedding_dimension()


# ── Public API ────────────────────────────────────────────────────────────────


def embed_chunks(chunks: list[CodeChunk], batch_size: int = 64) -> list[list[float]]:
    """
    Generate embeddings for a list of code chunks.

    Parameters
    ----------
    chunks : list[CodeChunk]
        The chunks to embed. Uses each chunk's `content` field.
    batch_size : int
        How many chunks to encode at once (for GPU/memory efficiency).

    Returns
    -------
    list[list[float]]
        One embedding vector per chunk, in the same order.
    """
    if not chunks:
        return []

    model = _get_model()

    # Extract the content strings
    texts = [chunk.content for chunk in chunks]

    logger.info(
        "Generating embeddings for %d chunks (batch_size=%d)",
        len(texts), batch_size,
    )

    # sentence-transformers handles batching internally
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        normalize_embeddings=True,  # L2-normalised → cosine = dot product
    )

    # Convert numpy arrays to plain Python lists for serialisation
    result = [emb.tolist() for emb in embeddings]

    logger.info("Embeddings generated: %d vectors of dim %d", len(result), len(result[0]))
    return result


def embed_query(query: str) -> list[float]:
    """
    Embed a single query string for search.

    Uses the same model as chunk embedding so vectors are in the
    same space and comparable.

    Parameters
    ----------
    query : str
        The user's search query.

    Returns
    -------
    list[float]
        The query embedding vector.
    """
    model = _get_model()
    embedding = model.encode(
        query,
        normalize_embeddings=True,
    )
    return embedding.tolist()
