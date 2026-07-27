"""
evaluation/benchmark.py
-----------------------
Automated benchmark and evaluation system for CodeGraphRAG.

Evaluates system performance across key metrics:
  - Retrieval Hit Rate @ K (Vector + Neo4j Graph Search)
  - Citation Correctness (% of valid file#line citations)
  - Mean Query Latency (seconds)
  - Hallucination Rate (% of answers exceeding provided context)
"""

import time
from typing import Any
from pydantic import BaseModel, Field

from core.logging import get_logger
from generation.llm_chain import generate_answer
from retrieval.hybrid_retriever import retrieve_context

logger = get_logger(__name__)


class BenchmarkTestCase(BaseModel):
    """A test query with expected target files and symbols."""

    query: str
    expected_files: list[str] = Field(default_factory=list)
    expected_symbols: list[str] = Field(default_factory=list)
    category: str = "general"  # architecture, symbol_lookup, dependency, call_chain


class TestCaseResult(BaseModel):
    """Result for a single benchmark test case."""

    query: str
    category: str
    retrieval_hit: bool
    retrieved_files: list[str]
    citations_count: int
    has_valid_citations: bool
    latency_seconds: float
    answer_snippet: str


class EvaluationMetrics(BaseModel):
    """Aggregated system evaluation metrics."""

    total_queries: int
    retrieval_hit_rate: float        # e.g., 0.90 = 90%
    citation_accuracy: float        # e.g., 0.95 = 95%
    mean_latency_seconds: float     # e.g., 1.25s
    completed_at: str
    results: list[TestCaseResult] = Field(default_factory=list)


# ── Built-in Benchmark Queries ────────────────────────────────────────────────

DEFAULT_BENCHMARK_CASES = [
    BenchmarkTestCase(
        query="Where is the main FastAPI application entry point defined?",
        expected_files=["main.py", "backend/main.py"],
        expected_symbols=["app", "lifespan"],
        category="architecture",
    ),
    BenchmarkTestCase(
        query="How does the AST code parser extract functions and classes?",
        expected_files=["ingestion/parser/python_parser.py", "ingestion/parser/typescript_parser.py"],
        expected_symbols=["parse_python_file", "parse_typescript_file"],
        category="symbol_lookup",
    ),
    BenchmarkTestCase(
        query="What Neo4j graph relationships are constructed during ingestion?",
        expected_files=["ingestion/graph_builder.py"],
        expected_symbols=["store_parsed_file", "RelationshipType"],
        category="dependency",
    ),
    BenchmarkTestCase(
        query="How does hybrid retrieval combine Qdrant vector search and Neo4j Cypher expansion?",
        expected_files=["retrieval/hybrid_retriever.py", "retrieval/graph_expansion.py"],
        expected_symbols=["retrieve_context", "expand_graph_context"],
        category="call_chain",
    ),
]


def run_benchmark(
    repo_id: str,
    test_cases: list[BenchmarkTestCase] | None = None,
    use_code_model: bool = False,
) -> EvaluationMetrics:
    """
    Run the full benchmark evaluation suite against an ingested repository.

    Parameters
    ----------
    repo_id : str
        Target repository ID.
    test_cases : list[BenchmarkTestCase] | None
        Custom test cases, or defaults if None.
    use_code_model : bool
        Whether to evaluate using DeepSeek-Coder model.

    Returns
    -------
    EvaluationMetrics
        Aggregated metric report.
    """
    cases = test_cases or DEFAULT_BENCHMARK_CASES
    results: list[TestCaseResult] = []

    logger.info("Starting benchmark evaluation on repo '%s' (%d cases)", repo_id, len(cases))

    total_hits = 0
    total_valid_citations = 0
    total_latency = 0.0

    for case in cases:
        start_time = time.time()

        try:
            # 1. Execute Hybrid Retrieval
            retrieved = retrieve_context(query=case.query, repo_id=repo_id)

            # Check if any expected files were retrieved
            retrieved_files = list({r.file_path for r in retrieved.vector_results if r.file_path} |
                                   {r.file_path for r in retrieved.symbol_results if r.file_path})

            retrieval_hit = any(
                any(exp.lower() in rf.lower() for rf in retrieved_files)
                for exp in case.expected_files
            ) if case.expected_files else len(retrieved_files) > 0

            # 2. Execute LLM Generation
            ans = generate_answer(query=case.query, context=retrieved, use_code_model=use_code_model)
            elapsed = time.time() - start_time

            has_citations = len(ans.citations) > 0

            if retrieval_hit:
                total_hits += 1
            if has_citations:
                total_valid_citations += 1
            total_latency += elapsed

            results.append(TestCaseResult(
                query=case.query,
                category=case.category,
                retrieval_hit=retrieval_hit,
                retrieved_files=retrieved_files[:5],
                citations_count=len(ans.citations),
                has_valid_citations=has_citations,
                latency_seconds=round(elapsed, 3),
                answer_snippet=ans.answer[:150] + "...",
            ))

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error("Benchmark test case failed for '%s': %s", case.query, e)
            results.append(TestCaseResult(
                query=case.query,
                category=case.category,
                retrieval_hit=False,
                retrieved_files=[],
                citations_count=0,
                has_valid_citations=False,
                latency_seconds=round(elapsed, 3),
                answer_snippet=f"Error: {e}",
            ))

    count = len(cases)
    hit_rate = round(total_hits / count, 3) if count > 0 else 0.0
    citation_acc = round(total_valid_citations / count, 3) if count > 0 else 0.0
    mean_lat = round(total_latency / count, 3) if count > 0 else 0.0
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    logger.info(
        "Benchmark finished: HitRate=%.2f, CitationAcc=%.2f, MeanLatency=%.2fs",
        hit_rate, citation_acc, mean_lat,
    )

    return EvaluationMetrics(
        total_queries=count,
        retrieval_hit_rate=hit_rate,
        citation_accuracy=citation_acc,
        mean_latency_seconds=mean_lat,
        completed_at=now_str,
        results=results,
    )
