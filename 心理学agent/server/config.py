"""
配置管理——环境变量 + 默认值
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # LLM Provider: "anthropic" | "deepseek"
    llm_provider: str = "anthropic"

    # API Keys
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"

    # 模型配置
    main_model: str = "claude-sonnet-4-20250514"
    light_model: str = "claude-haiku-4-20250414"
    deepseek_model: str = "deepseek-chat"
    max_tokens: int = 2048

    # 服务配置
    env: str = "development"
    log_level: str = "info"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True

    # CORS
    cors_origins: list[str] = ["*"]

    # JWT 认证
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24小时

    # ChromaDB
    chroma_persist_dir: str = "./data/chroma"
    chromadb_host: str = ""
    chromadb_port: int = 8001

    # SQLite
    sqlite_db_path: str = "./data/agent.db"

    # 多模态
    tts_provider: str = "openai"
    upload_dir: str = ""
    max_file_size: int = 10 * 1024 * 1024  # 10MB

    # 对话限制
    max_conversation_turns: int = 50

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
