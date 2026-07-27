"""
api/routes/query.py
-------------------
REST API endpoints for querying an ingested codebase.

Endpoints:
  POST /api/query — submit natural language questions and get grounded answers with file citations.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.logging import get_logger
from generation.llm_chain import QueryAnswer, generate_answer
from retrieval.hybrid_retriever import retrieve_context

logger = get_logger(__name__)

router = APIRouter()


class QueryRequest(BaseModel):
    """Request body for submitting codebase queries."""

    query: str = Field(..., description="Natural language question about the codebase")
    repo_id: str = Field(..., description="Target repository identifier (e.g., 'owner/repo' or 'zip/name')")
    use_code_model: bool = Field(default=False, description="Use DeepSeek-Coder LLM model if True")


class QueryResponse(BaseModel):
    """API response containing answer, citations, and graph context metadata."""

    query: str
    repo_id: str
    answer: str
    citations: list[str]
    model_used: str
    graph_nodes_count: int


@router.post("/query", response_model=QueryResponse)
async def query_codebase(request: QueryRequest):
    """
    Query an ingested codebase using hybrid retrieval & LLM generation.

    Performs:
      1. Vector search + Neo4j symbol search
      2. 1-2 hop Cypher graph expansion
      3. Groq LLM answer generation with mandatory file citations
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query string cannot be empty.")

    if not request.repo_id.strip():
        raise HTTPException(status_code=400, detail="repo_id must be provided.")

    logger.info("Received query for repo '%s': '%s'", request.repo_id, request.query)

    try:
        # 1. Hybrid Retrieval (Vector + Neo4j Graph)
        retrieved_context = retrieve_context(
            query=request.query,
            repo_id=request.repo_id,
        )

        # 2. LLM Generation
        answer_result = generate_answer(
            query=request.query,
            context=retrieved_context,
            use_code_model=request.use_code_model,
        )

        return QueryResponse(
            query=request.query,
            repo_id=request.repo_id,
            answer=answer_result.answer,
            citations=answer_result.citations,
            model_used=answer_result.model_used,
            graph_nodes_count=len(retrieved_context.graph_context),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("Query execution failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")
