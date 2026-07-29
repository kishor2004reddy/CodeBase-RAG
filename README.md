# 🧠 CodeBase RAG

> **Structure-Aware Multi-Language Codebase Intelligence** — Chat with your codebase using AST parsing, knowledge graphs, and hybrid retrieval.

CodeBase RAG is an open-source, production-ready **Retrieval-Augmented Generation (RAG)** system that lets you ask natural language questions about any Python or TypeScript repository and get grounded, citation-backed answers.

Unlike plain vector search tools, CodeBase RAG parses code using **Abstract Syntax Trees (AST)**, builds a **Neo4j dependency knowledge graph**, and performs **hybrid + graph-enhanced retrieval** to answer architecture-level and symbol-level questions with exact file-line citations — minimizing hallucinations by design.

---

## ✨ Features

### 🔹 Structure-Aware AST Parsing
- Uses **Tree-sitter** (Python & TypeScript grammars) to parse source files into ASTs
- Extracts code at the **function**, **class**, **method**, and **file-summary** level — no arbitrary text splitting
- Captures **signatures**, **docstrings**, **decorators**, and **parent class** information for each symbol

### 🔹 Neo4j Knowledge Graph
- Builds a **code dependency graph** with typed edges:
  - `DEFINES` — File defines a Symbol
  - `IMPORTS` — File imports a module
  - `CALLS` — Function/file calls another symbol
  - `INHERITS` — Class inherits from another class
  - `EXPORTS` — File exports a symbol
- Supports **1–2 hop Cypher traversals** for architecture-level multi-hop reasoning

### 🔹 Hybrid Retrieval Pipeline
- **Vector Similarity Search** via Qdrant — semantic nearest-neighbour over embedded code chunks
- **Exact/Fuzzy Symbol Search** via Neo4j — precise lookup of functions, classes, and methods by name
- **Graph Expansion** — seed files and symbols are expanded through the dependency graph for richer context

### 🔹 Dual-Model LLM Generation (Groq)
- **LLaMA 3.3 70B** (`llama-3.3-70b-versatile`) — general-purpose codebase Q&A
- **DeepSeek-R1 Distill LLaMA 70B** (`deepseek-r1-distill-llama-70b`) — code-specialised reasoning
- Switchable per-query via the `use_code_model` flag in the API

### 🔹 Persistent Multi-Turn Conversations (LangGraph + Redis)
- Powered by **LangGraph StateGraph** with a `RedisSaver` checkpointer
- Conversation history **survives server restarts** (persisted in Redis)
- Each session is fully isolated by `session_id` (UUID)
- **Auto-TTL**: inactive sessions expire after 7 days (configurable)
- **History cap**: last 20 turns are injected to avoid token overflow

### 🔹 Time-Travel / Session Rollback
- Every query creates a **checkpoint** in Redis
- Roll back any session to any prior checkpoint via the API
- `GET /api/session/{session_id}/history` — list all checkpoints
- `POST /api/session/{session_id}/rollback/{checkpoint_id}` — restore a past state

### 🔹 Hallucination Reduction
- LLM is **strictly grounded** on retrieved context only
- Mandatory **file-path citations** in every answer (`[filepath#Lstart-Lend]`)
- Graceful fallback: *"Based on the indexed codebase context, I cannot find enough details to answer this question."*
- Low temperature (0.2) for factual, deterministic answers

### 🔹 Dual Ingestion Sources
- **GitHub URL** — shallow-clones the repo, runs the full pipeline, then cleans up
- **ZIP Upload** — extracts an uploaded `.zip` archive and processes it the same way
- Re-ingestion is safe: previous data (Qdrant vectors + Neo4j graph) is automatically cleared before re-processing

### 🔹 Evaluation & Benchmarking
- Built-in benchmark runner (`evaluation/benchmark.py`)
- Measures **retrieval accuracy**, **citation correctness**, **context precision**, **hallucination rate**, and **query latency**

### 🔹 React Frontend
- Single-page app built with **React 19 + TypeScript + Vite**
- **ChatPanel** — multi-turn chat interface with message history
- **RepoInput** — GitHub URL / ZIP upload form with ingestion status
- **Sidebar** — session management, history, and navigation
- **GraphDrawer** — visual dependency graph explorer
- **EvalDashboard** — live evaluation metrics view
- **StatusBar** — real-time backend connectivity indicator

### 🔹 Fully Dockerized
- Single `docker compose up` starts all five services:
  - FastAPI backend (port `8000`)
  - React frontend (port `5173`)
  - Qdrant vector database (ports `6333`, `6334`)
  - Neo4j graph database (ports `7474`, `7687`)
  - Redis Stack with RedisInsight UI (ports `6379`, `8001`)

---

## 🏗️ Architecture

### Ingestion Pipeline

```
GitHub URL / ZIP File
  → Clone / Extract
  → Discover .py / .ts files
  → AST Parsing (Tree-sitter)
  → Symbol Extraction (functions, classes, methods)
  → Neo4j Graph Construction (DEFINES / IMPORTS / CALLS / INHERITS / EXPORTS edges)
  → Function/Class-Level Chunking
  → Embedding Generation (BAAI/bge-small-en-v1.5)
  → Qdrant Vector Storage
```

### Query Pipeline

```
User Query
  → Hybrid Retrieval:
      • Vector Similarity Search (Qdrant)
      • Exact Symbol Search (Neo4j)
      • Graph Expansion / 1–2 hop Cypher traversals
  → Context Assembly & Deduplication
  → LangGraph RAG StateGraph (retrieve_node → generate_node)
  → ChatGroq (LLaMA 3.3 / DeepSeek-R1)
  → Answer + Mandatory File Citations
  → RedisSaver Checkpoint (conversation persisted)
```

### LangGraph State Topology

```
START → [retrieve_node] → [generate_node] → END
              ↓                   ↓
         Qdrant + Neo4j     ChatGroq (Groq API)
              ↓                   ↓
         RetrievedContext    Redis Checkpoint
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend API** | FastAPI 0.140+, Uvicorn, Python 3.11+ |
| **LLM Orchestration** | LangGraph, LangChain Core, LangChain-Groq |
| **LLM Provider** | Groq API (LLaMA 3.3 70B + DeepSeek-R1 70B) |
| **Code Parsing** | Tree-sitter (Python & TypeScript grammars) |
| **Vector Database** | Qdrant (self-hosted via Docker) |
| **Graph Database** | Neo4j 5 Community + APOC |
| **Session Memory** | Redis Stack + LangGraph RedisSaver |
| **Embeddings** | Sentence Transformers — `BAAI/bge-small-en-v1.5` |
| **Frontend** | React 19, TypeScript, Vite 8 |
| **Containerization** | Docker & Docker Compose |
| **Data Validation** | Pydantic v2, Pydantic-Settings |

---

## 📡 API Reference

### Ingestion

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/ingest/github` | Ingest a repo from a GitHub HTTPS URL |
| `POST` | `/api/ingest/zip` | Ingest a repo from an uploaded `.zip` file |
| `GET` | `/api/ingest/status` | Check if a repository has been ingested |

### Query & Chat

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/query` | Submit a natural language query and receive a grounded answer |
| `GET` | `/api/session/{session_id}/history` | List all checkpoints for a session |
| `POST` | `/api/session/{session_id}/rollback/{checkpoint_id}` | Roll back a session to a prior checkpoint |
| `DELETE` | `/api/session/{session_id}` | Permanently delete a session from Redis |

### System

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check — returns app version and environment |
| `GET` | `/docs` | Swagger UI (interactive API docs) |
| `GET` | `/redoc` | ReDoc API documentation |

### Evaluation

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/eval/run` | Run the benchmark suite against an ingested repo |

---

## 🚀 Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/)
- A free [Groq API key](https://console.groq.com)

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/CodeBase-RAG.git
cd CodeBase-RAG
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

Open `.env` and fill in your Groq API key:

```env
GROQ_API_KEY=your_groq_api_key_here
```

All other values are pre-configured for Docker Compose and do not need to be changed for local development.

### 3. Start All Services

```bash
docker compose up -d
```

This starts:

| Service | URL |
|---|---|
| React Frontend | http://localhost:5173 |
| FastAPI Backend | http://localhost:8000 |
| Swagger API Docs | http://localhost:8000/docs |
| Qdrant Dashboard | http://localhost:6333/dashboard |
| Neo4j Browser | http://localhost:7474 |
| RedisInsight UI | http://localhost:8001 |

### 4. Ingest a Repository

```bash
curl -X POST http://localhost:8000/api/ingest/github \
  -H "Content-Type: application/json" \
  -d '{"github_url": "https://github.com/fastapi/fastapi"}'
```

### 5. Query Your Codebase

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How does authentication work?",
    "repo_id": "fastapi/fastapi"
  }'
```

---

## 🔧 Local Development (Without Docker)

### Backend

Requirements: Python 3.11+, [uv](https://github.com/astral-sh/uv)

```bash
cd backend
uv sync
uv run uvicorn main:app --reload
```

> Make sure Qdrant, Neo4j, and Redis are running separately or via `docker compose up qdrant neo4j redis -d`.

### Frontend

Requirements: Node.js 20+

```bash
cd frontend
npm install
npm run dev
```

---

## ⚙️ Configuration

All settings are loaded from `.env` (or environment variables). Key options:

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | *(required)* | Groq API key — get free at console.groq.com |
| `GROQ_MODEL_GENERAL` | `llama-3.3-70b-versatile` | Model for general Q&A |
| `GROQ_MODEL_CODE` | `deepseek-r1-distill-llama-70b` | Model for code-specific reasoning |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant vector DB URL |
| `QDRANT_COLLECTION` | `codebase` | Qdrant collection name |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j connection URI |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | HuggingFace embedding model |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `SESSION_TTL_MINUTES` | `10080` (7 days) | Session expiry time |
| `MAX_HISTORY_TURNS` | `20` | Max conversation turns injected into LLM |
| `APP_ENV` | `development` | Application environment |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## 📁 Project Structure

```
CodeBase-RAG/
├── backend/
│   ├── main.py                  # FastAPI app entry point + lifespan startup
│   ├── core/
│   │   ├── config.py            # Pydantic-Settings configuration
│   │   ├── rag_graph.py         # LangGraph StateGraph (retrieve → generate)
│   │   └── logging.py           # Structured logging setup
│   ├── api/routes/
│   │   ├── ingest.py            # POST /api/ingest/github|zip
│   │   ├── query.py             # POST /api/query + session management
│   │   └── eval.py              # POST /api/eval/run
│   ├── ingestion/
│   │   ├── repo_fetcher.py      # Git clone + ZIP extraction
│   │   ├── parser/              # AST parsers (Python + TypeScript)
│   │   ├── graph_builder.py     # Neo4j symbol/relationship storage
│   │   ├── chunker.py           # Function/class-level code chunking
│   │   ├── embedder.py          # Sentence Transformer embeddings
│   │   └── storage.py           # Qdrant vector upsert/delete
│   ├── retrieval/
│   │   ├── hybrid_retriever.py  # Orchestrates vector + symbol + graph retrieval
│   │   ├── vector_search.py     # Qdrant semantic search
│   │   ├── symbol_search.py     # Neo4j exact/fuzzy symbol lookup
│   │   └── graph_expansion.py   # 1–2 hop Cypher graph traversal
│   ├── generation/
│   │   └── llm_chain.py         # LangChain ChatGroq chain + prompt template
│   └── evaluation/
│       └── benchmark.py         # Benchmark runner + metrics
├── frontend/
│   └── src/
│       ├── App.tsx              # Main app + routing
│       ├── components/
│       │   ├── ChatPanel.tsx    # Multi-turn chat UI
│       │   ├── RepoInput.tsx    # GitHub URL / ZIP upload form
│       │   ├── Sidebar.tsx      # Session management sidebar
│       │   ├── GraphDrawer.tsx  # Dependency graph visualizer
│       │   ├── EvalDashboard.tsx # Evaluation metrics view
│       │   ├── Message.tsx      # Chat message renderer
│       │   └── StatusBar.tsx    # Backend status indicator
│       └── api/                 # Typed API client functions
├── docker-compose.yml           # Full stack orchestration
├── .env.example                 # Environment variable template
└── README.md
```

---

## 💡 Example Queries

Once a repository is ingested, you can ask questions like:

- *"How does authentication work in this codebase?"*
- *"Where is `UserService` defined and what methods does it expose?"*
- *"What is the call chain from the API layer to the database?"*
- *"Which files import the `config` module?"*
- *"What classes inherit from `BaseModel`?"*
- *"Explain the ingestion pipeline step by step."*

Each answer includes exact file-line citations, e.g.:

```
The authentication flow is handled in [backend/auth/middleware.py#L24-L68]
which calls the JWT validator defined in [backend/auth/jwt.py#L10-L35].
```

---

## 📊 Evaluation Metrics

The built-in benchmark measures:

| Metric | Description |
|---|---|
| **Retrieval Accuracy** | % of relevant chunks retrieved |
| **Citation Correctness** | % of answers with valid file citations |
| **Context Precision** | Signal-to-noise ratio of retrieved context |
| **Hallucination Rate** | % of answers containing fabricated facts |
| **Query Latency** | End-to-end response time (ms) |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add my feature'`)
4. Push the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
