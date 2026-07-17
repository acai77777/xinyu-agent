"""
配置管理——环境变量 + 默认值
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # LLM Provider: "anthropic" | "deepseek" | "openrouter" | "volcengine"
    llm_provider: str = "openrouter"

    # API Keys
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    volcengine_api_key: str = ""
    volcengine_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    volc_asr_app_key: str = ""
    volc_asr_access_key: str = ""
    volc_asr_resource_id: str = "volc.seedasr.auc"
    volc_asr_submit_url: str = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit"
    volc_asr_query_url: str = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/query"

    # 模型配置
    main_model: str = "doubao-seed-2-0-mini-260428"
    light_model: str = "deepseek/deepseek-v3.2"
    deepseek_model: str = "deepseek-chat"
    # 推理模型 max_tokens 分级（含推理 token 占用）
    small_max_tokens: int = 1024    # 短判断/分类
    medium_max_tokens: int = 2048   # 中等生成
    large_max_tokens: int = 4096    # 长生成
    main_max_tokens: int = 1024     # 主对话——给 LLM 完整收尾余量,字数靠 prompt 硬约束控
    llm_timeout: int = 60  # LLM 调用超时秒数

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

    # 对话压缩
    compress_threshold: int = 8         # 超过此轮数触发压缩(第 9 轮首次触发)
    compress_keep_recent: int = 3       # 保留最近 N 轮原始对话(原 6,减少长回复风格污染)
    sub_agent_timeout: int = 15         # 子 Agent 最大等待秒数（推理模型单次 5-7s，留余量）

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
