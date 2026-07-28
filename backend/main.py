from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.logging import configure_logging, get_logger


# ── Logging — initialise before anything else uses it ────────────────────────

configure_logging(settings.log_level)
logger = get_logger(__name__)


# ── Lifespan: runs on startup & shutdown ────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """Startup checks before the server begins accepting requests."""

    # Verify Qdrant is reachable
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(url=settings.qdrant_url, timeout=5)
        client.get_collections()
        logger.info("Qdrant connected at %s", settings.qdrant_url)
    except Exception as e:
        logger.warning("Qdrant not reachable: %s", e)
        logger.warning("Start Qdrant with: docker compose up qdrant -d")

    # Verify Neo4j is reachable
    try:
        from ingestion.graph_builder import get_neo4j_driver
        driver = get_neo4j_driver()
        driver.verify_connectivity()
        server_info = driver.get_server_info()
        logger.info(
            "Neo4j connected at %s (v%s)",
            settings.neo4j_uri, server_info.agent,
        )
    except Exception as e:
        logger.warning("Neo4j not reachable: %s", e)
        logger.warning("Start Neo4j with: docker compose up neo4j -d")

    # Verify Redis is reachable
    try:
        import redis as redis_lib
        r = redis_lib.from_url(settings.redis_url, socket_connect_timeout=5)
        r.ping()
        logger.info("Redis connected at %s", settings.redis_url)
    except Exception as e:
        logger.warning("Redis not reachable: %s", e)
        logger.warning("Start Redis with: docker compose up redis -d")

    # Verify Groq API key is set
    if not settings.groq_api_key:
        logger.warning(
            "GROQ_API_KEY is not set — LLM generation will fail. "
            "Add it to your .env file. Get a free key at https://console.groq.com"
        )
    else:
        logger.info(
            "Groq API key loaded (model: %s)", settings.groq_model_general
        )

    # Initialise LangGraph RAG graph + RedisSaver checkpointer
    try:
        from core.rag_graph import init_rag_graph
        init_rag_graph()
    except Exception as e:
        logger.warning("LangGraph graph initialisation failed: %s", e)
        logger.warning("Ensure Redis is running before starting the backend.")

    logger.info("CodeGraphRAG startup complete — accepting requests")
    yield  # Server is now running

    # Shutdown cleanup
    try:
        from ingestion.graph_builder import close_neo4j_driver
        close_neo4j_driver()
    except Exception:
        pass
    logger.info("CodeGraphRAG shutting down...")


# ── App instance ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="CodeGraphRAG",
    description=(
        "Structure-aware RAG system for intelligently querying codebases "
        "using AST parsing, knowledge graphs, and hybrid retrieval."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ── CORS — allow React dev server ────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",   # fallback
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ────────────────────────────────────────────────────────────────────

from api.routes.ingest import router as ingest_router
from api.routes.query import router as query_router
from api.routes.eval import router as eval_router

app.include_router(ingest_router, prefix="/api", tags=["Ingestion"])
app.include_router(query_router, prefix="/api", tags=["Query"])
app.include_router(eval_router, prefix="/api", tags=["Evaluation"])


# ── Health check ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health_check():
    """Quick health check — confirms the server is running."""
    return {
        "status": "ok",
        "app": "CodeGraphRAG",
        "version": "0.1.0",
        "env": settings.app_env,
    }
