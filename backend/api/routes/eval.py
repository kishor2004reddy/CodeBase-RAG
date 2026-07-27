"""
api/routes/eval.py
------------------
REST API endpoints for triggering system benchmark evaluation and viewing metrics.

Endpoints:
  POST /api/eval/run    — run automated benchmark evaluation on a repo
  GET  /api/eval/latest — get latest benchmark results
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.logging import get_logger
from evaluation.benchmark import EvaluationMetrics, run_benchmark

logger = get_logger(__name__)

router = APIRouter()

# In-memory cache for latest evaluation results
_latest_eval: EvaluationMetrics | None = None


class EvalRunRequest(BaseModel):
    """Request payload to trigger benchmark evaluation."""

    repo_id: str = Field(..., description="Target repository ID to evaluate")
    use_code_model: bool = Field(default=False, description="Use DeepSeek-Coder model if True")


@router.post("/eval/run", response_model=EvaluationMetrics)
async def run_evaluation(request: EvalRunRequest):
    """
    Run automated benchmark evaluation suite on an ingested repository.

    Measures:
      - Retrieval Hit Rate @ K
      - Citation Accuracy
      - Mean Query Latency
    """
    global _latest_eval

    if not request.repo_id.strip():
        raise HTTPException(status_code=400, detail="repo_id must be specified.")

    logger.info("Received request to run benchmark on repo '%s'", request.repo_id)

    try:
        metrics = run_benchmark(
            repo_id=request.repo_id,
            use_code_model=request.use_code_model,
        )
        _latest_eval = metrics
        return metrics

    except Exception as e:
        logger.error("Benchmark evaluation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {e}")


@router.get("/eval/latest", response_model=EvaluationMetrics)
async def get_latest_evaluation():
    """Get the latest benchmark evaluation metrics."""
    if _latest_eval is None:
        raise HTTPException(status_code=404, detail="No evaluation benchmark has been run yet.")
    return _latest_eval
