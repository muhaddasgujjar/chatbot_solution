from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "OU Chatbot API"
    app_env: str = "development"
    api_prefix: str = "/api"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    llm_provider: str = "groq"
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"

    chroma_persist_dir: str = "./chroma_db"
    top_k: int = 3
    min_confidence_score: float = 0.6
    confidence_score_scale: float = 2.5
    rerank_semantic_weight: float = 0.5
    rerank_keyword_weight: float = 0.2
    rerank_source_url_weight: float = 0.2
    rerank_short_chunk_penalty: float = 0.05
    rerank_long_chunk_penalty: float = 0.03
    feedback_store_path: str = "./chat_feedback.jsonl"
    chat_store_path: str = "./chat_history.jsonl"
    allowed_ingest_domains: str = "oakland.edu,support.oakland.edu"
    ingest_max_docx_files: int = 1000
    ingest_max_crawl_pages: int = 1000

    tdx_base_url: str = ""
    tdx_api_token: str = ""
    tdx_articles_path: str = "/api/v1/knowledgebase/search"
    tdx_ticket_create_path: str = "/api/v1/tickets"
    tdx_timeout_seconds: float = 20.0
    tdx_max_retries: int = 2
    purechat_widget_id: str = ""
    rate_limit_per_minute: int = 60
    auth_enabled: bool = False
    entra_issuer: str = ""
    entra_audience: str = ""
    entra_jwks_url: str = ""
    entra_jwt_algorithms: str = "RS256,HS256"
    entra_test_hs256_secret: str = ""


settings = Settings()
