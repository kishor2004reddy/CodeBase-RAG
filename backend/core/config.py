from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Groq LLM API
    groq_api_key: str = ""
    groq_model_general: str = "llama-3.3-70b-versatile"
    groq_model_code: str = "deepseek-r1-distill-llama-70b"

    # Qdrant vector database
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "codebase"

    # Neo4j graph database
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = ""
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"

    # Embeddings
    embedding_model: str = "BAAI/bge-small-en-v1.5"

    # Ingestion
    tmp_repo_dir: str = "tmp_repos"
    tmp_zip_dir: str = "tmp_zips"

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    # Redis — session memory + LangGraph checkpointing
    redis_url: str = "redis://localhost:6379"
    session_ttl_minutes: int = 10080   # 7 days — sessions expire after inactivity
    max_history_turns: int = 20        # cap injected turns to avoid LLM token overflow


# Singleton instance — import this everywhere
settings = Settings()
