from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings


# ── Lifespan: runs on startup & shutdown ────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup checks before the server begins accepting requests."""
    # Verify Qdrant is reachable
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(url=settings.qdrant_url, timeout=5)
        client.get_collections()
        print(f"✅ Qdrant connected at {settings.qdrant_url}")
    except Exception as e:
        print(f"⚠️  Qdrant not reachable: {e}")
        print("   Start Qdrant with: docker compose up qdrant -d")

    # Verify Groq API key is set
    if not settings.groq_api_key:
        print("⚠️  GROQ_API_KEY is not set — LLM generation will fail.")
        print("   Add it to your .env file. Get a free key at https://console.groq.com")
    else:
        print(f"✅ Groq API key loaded (model: {settings.groq_model_general})")

    yield  # Server is now running

    # Shutdown cleanup (if needed in future)
    print("🛑 Shutting down CodeGraphRAG...")


# ── App instance ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="CodeGraphRAG",
    description="Structure-aware RAG system for intelligently querying codebases using AST parsing, knowledge graphs, and hybrid retrieval.",
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

# Routers will be added here as we build each phase:
# from api.routes.ingest import router as ingest_router
# from api.routes.query import router as query_router
# app.include_router(ingest_router, prefix="/api", tags=["Ingestion"])
# app.include_router(query_router, prefix="/api", tags=["Query"])


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
