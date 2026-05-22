"""Configuration handling for the app. Will load environment variables and defaults."""
from functools import lru_cache

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Advanced RAG System"
    debug: bool = True

    groq_api_key: str | None = None
    # Default to None so the running server doesn't assume a model the API
    # key may not have access to. Set via env `GROQ_MODEL` or override per request.
    groq_model: str | None = None
    gemini_api_key: str | None = None
    chroma_api_url: str | None = None
    web_search_api_url: str | None = None
    document_processing_api_url: str | None = None
    redis_url: str | None = None
    use_sqlite_memory: bool = False
    sqlite_db_path: str = "memory.db"
    database_path: str = "app.db"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
