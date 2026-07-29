"""
api/routes/ingest.py
--------------------
REST API endpoints for ingesting repositories.

Endpoints:
  POST   /api/ingest/github   — ingest from a GitHub URL
  POST   /api/ingest/zip      — ingest from an uploaded ZIP file
  GET    /api/ingest/status   — check if a repo has been ingested
  DELETE /api/repo/{repo_id}  — permanently delete a repo's indexed data
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ── Request / Response models ─────────────────────────────────────────────────


class GitHubIngestRequest(BaseModel):
    """Request body for GitHub URL ingestion."""
    github_url: str = Field(..., description="HTTPS GitHub repository URL")


class IngestResponse(BaseModel):
    """Response after ingestion completes."""
    repo_id: str
    status: str
    files_processed: int
    symbols_extracted: int
    chunks_created: int
    message: str


class DeleteRepoResponse(BaseModel):
    """Response after deleting a repository's indexed data."""
    repo_id: str
    message: str


# ── Pipeline orchestrator ─────────────────────────────────────────────────────


def _run_ingestion_pipeline(repo_dir: Path, repo_id: str) -> IngestResponse:
    """
    Run the full ingestion pipeline on a local repository directory.

    Steps:
      1. Discover source files
      2. Parse each file (AST)
      3. Store symbols + relationships in Neo4j
      4. Chunk code into embeddable units
      5. Generate embeddings
      6. Store vectors in Qdrant

    Parameters
    ----------
    repo_dir : Path
        Local path to the repository.
    repo_id : str
        Unique identifier for this ingestion.

    Returns
    -------
    IngestResponse
        Summary of what was processed.
    """
    from ingestion.repo_fetcher import discover_files
    from ingestion.parser import parse_file
    from ingestion.graph_builder import setup_schema, store_parsed_file, clear_repo_graph
    from ingestion.chunker import chunk_parsed_file
    from ingestion.embedder import embed_chunks, get_embedding_dimension
    from ingestion.storage import ensure_collection, upsert_chunks, delete_repo_vectors

    # ── Step 0: Clean up any previous data for this repo ──────────────
    logger.info("Clearing previous data for repo %s", repo_id)
    clear_repo_graph(repo_id)
    delete_repo_vectors(repo_id)

    # ── Step 1: Discover files ────────────────────────────────────────
    source_files = discover_files(repo_dir)
    if not source_files:
        raise HTTPException(
            status_code=400,
            detail="No Python or TypeScript files found in the repository.",
        )

    logger.info("Found %d source files to process", len(source_files))

    # ── Step 2: Setup Neo4j schema ────────────────────────────────────
    setup_schema()

    # ── Step 3: Setup Qdrant collection ───────────────────────────────
    vector_dim = get_embedding_dimension()
    ensure_collection(vector_dim)

    # ── Step 4: Parse → Graph → Chunk → Embed → Store ────────────────
    total_symbols = 0
    all_chunks = []

    for sf in source_files:
        try:
            # Read the file
            source_code = Path(sf.absolute_path).read_text(encoding="utf-8", errors="replace")

            # Parse with AST
            parsed = parse_file(source_code, sf.relative_path, sf.language)
            total_symbols += len(parsed.symbols)

            # Store in Neo4j graph
            store_parsed_file(parsed, repo_id)

            # Create chunks
            chunks = chunk_parsed_file(parsed, repo_id)
            all_chunks.extend(chunks)

            logger.debug(
                "Processed %s: %d symbols, %d chunks",
                sf.relative_path, len(parsed.symbols), len(chunks),
            )

        except Exception as e:
            logger.error("Failed to process %s: %s", sf.relative_path, e)
            continue  # Skip this file, continue with others

    # ── Step 5: Generate embeddings for all chunks ────────────────────
    if all_chunks:
        logger.info("Embedding %d chunks...", len(all_chunks))
        embeddings = embed_chunks(all_chunks)

        # ── Step 6: Store in Qdrant ───────────────────────────────────
        upsert_chunks(all_chunks, embeddings)

    logger.info(
        "Ingestion complete: %d files, %d symbols, %d chunks",
        len(source_files), total_symbols, len(all_chunks),
    )

    return IngestResponse(
        repo_id=repo_id,
        status="completed",
        files_processed=len(source_files),
        symbols_extracted=total_symbols,
        chunks_created=len(all_chunks),
        message=f"Successfully ingested {len(source_files)} files with {total_symbols} symbols.",
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/ingest/github", response_model=IngestResponse)
async def ingest_github(request: GitHubIngestRequest):
    """
    Ingest a repository from a GitHub URL.

    Clones the repo (shallow), runs the full ingestion pipeline,
    then cleans up the clone directory.
    """
    from ingestion.repo_fetcher import clone_repo, cleanup_repo

    # Generate a repo ID from the URL
    url = request.github_url.strip().rstrip("/")
    repo_name = url.split("/")[-1].replace(".git", "")
    owner = url.split("/")[-2] if "/" in url else "unknown"
    repo_id = f"{owner}/{repo_name}"

    logger.info("Starting GitHub ingestion: %s (repo_id=%s)", url, repo_id)

    try:
        # Clone
        repo_dir = clone_repo(url)

        # Run pipeline
        result = _run_ingestion_pipeline(repo_dir, repo_id)

        # Cleanup
        cleanup_repo(repo_dir)

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Ingestion failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")


@router.post("/ingest/zip", response_model=IngestResponse)
async def ingest_zip(file: UploadFile = File(...)):
    """
    Ingest a repository from an uploaded ZIP file.

    Extracts the ZIP, runs the full ingestion pipeline,
    then cleans up the temp directories.
    """
    from ingestion.repo_fetcher import extract_zip, cleanup_repo

    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Please upload a .zip file")

    # Save the uploaded file to disk
    zip_dir = Path(settings.tmp_zip_dir)
    zip_dir.mkdir(parents=True, exist_ok=True)
    zip_path = zip_dir / f"{uuid.uuid4().hex[:8]}_{file.filename}"

    try:
        content = await file.read()
        zip_path.write_bytes(content)

        # Extract
        repo_dir = extract_zip(zip_path)

        # Generate repo ID from the filename
        repo_name = file.filename.replace(".zip", "")
        repo_id = f"zip/{repo_name}"

        logger.info("Starting ZIP ingestion: %s (repo_id=%s)", file.filename, repo_id)

        # Run pipeline
        result = _run_ingestion_pipeline(repo_dir, repo_id)

        # Cleanup
        cleanup_repo(repo_dir)
        zip_path.unlink(missing_ok=True)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("ZIP ingestion failed: %s", e, exc_info=True)
        zip_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")


@router.delete("/repo/{repo_id:path}", response_model=DeleteRepoResponse)
async def delete_repo(repo_id: str):
    """
    Permanently delete a repository's indexed data.

    Removes the repo's Neo4j knowledge graph (symbols + relationships)
    and its Qdrant vectors. This does NOT delete any chat session/history —
    use DELETE /api/session/{session_id} for that.

    The `{repo_id:path}` converter allows repo_id values containing slashes
    (e.g. "owner/repo" from GitHub ingestion, or "zip/my-project" from ZIP
    uploads) to be passed as a single path segment.
    """
    from ingestion.graph_builder import clear_repo_graph
    from ingestion.storage import delete_repo_vectors

    if not repo_id.strip():
        raise HTTPException(status_code=400, detail="repo_id must be provided.")

    try:
        clear_repo_graph(repo_id)
        delete_repo_vectors(repo_id)
        logger.info("Deleted all indexed data for repo '%s'", repo_id)
        return DeleteRepoResponse(
            repo_id=repo_id,
            message=f"Successfully deleted all indexed data for '{repo_id}'.",
        )
    except Exception as e:
        logger.error("Failed to delete repo '%s': %s", repo_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete repo: {e}")
