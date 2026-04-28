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
    feedback_store_path: str = "./chat_feedback.jsonl"
    chat_store_path: str = "./chat_history.jsonl"
    allowed_ingest_domains: str = "oakland.edu,support.oakland.edu"

    tdx_base_url: str = ""
    tdx_api_token: str = ""
    tdx_articles_path: str = "/api/v1/knowledgebase/search"
    purechat_widget_id: str = ""
    rate_limit_per_minute: int = 60


settings = Settings()
