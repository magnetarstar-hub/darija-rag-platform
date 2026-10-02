from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All settings come from env vars prefixed RAG_ (or a .env file)."""

    model_config = SettingsConfigDict(env_prefix="RAG_", env_file=".env", extra="ignore")

    app_env: str = "dev"  # dev | test | prod
    database_url: str = "sqlite:///./dev.db"
    auto_create_tables: bool = False  # tests/dev only; production uses Alembic migrations

    redis_url: str = "redis://localhost:6379/0"
    queue_mode: str = "inline"  # inline (sync, dev/tests) | rq (Redis workers)
    queue_name: str = "ingest"

    qdrant_url: str | None = None  # None -> embedded local mode at qdrant_path
    qdrant_path: str = "data/qdrant"
    collection: str = "chunks"
    upload_dir: str = "data/uploads"

    jwt_secret: str = "change-me"
    jwt_expire_minutes: int = 60
    bootstrap_token: str | None = None  # if set, required to create tenants

    embedder: str = "bge"  # bge | hash (hash = lexical stand-in for tests/CI)
    embed_model: str = "BAAI/bge-m3"
    embed_dim: int = 1024
    reranker: str = "cross"  # cross | none
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    ollama_url: str = "http://localhost:11434"
    llm_model: str = "qwen2.5:7b-instruct"

    chunk_size: int = 800
    chunk_overlap: int = 120
    candidates_k: int = 20
    final_k: int = 5
    abstain_threshold: float = 0.35
    min_verifier_score: float = 0.3  # hard gate: below this, never answer, however strong retrieval looks

    max_upload_mb: int = 25
    max_docs_per_tenant: int = 500
    ask_rate_limit_per_min: int = 30
    login_rate_limit_per_min: int = 10

    otlp_endpoint: str | None = None  # e.g. http://jaeger:4317
