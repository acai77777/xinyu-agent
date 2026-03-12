"""
统一 LLM 客户端工厂——所有模块通过此模块调用 LLM
支持 Provider：anthropic / deepseek / openrouter
Light model 始终走 DeepSeek 官方直连
"""
from config import settings


def _is_openai_compatible() -> bool:
    """判断当前 provider 是否使用 OpenAI 兼容 API"""
    return settings.llm_provider in ("deepseek", "openrouter")


def get_async_client():
    """
    获取异步 LLM 客户端（主模型）。
    - anthropic → anthropic.AsyncAnthropic
    - deepseek / openrouter → openai.AsyncOpenAI
    """
    provider = settings.llm_provider

    if provider == "openrouter":
        from openai import AsyncOpenAI
        return AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )
    elif provider == "deepseek":
        from openai import AsyncOpenAI
        return AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
    else:
        import anthropic
        return anthropic.AsyncAnthropic()


def get_light_client():
    """获取轻量模型的异步客户端——始终走 DeepSeek 官方直连"""
    from openai import AsyncOpenAI
    return AsyncOpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )


def get_sync_client():
    """
    获取同步 LLM 客户端。
    - anthropic → anthropic.Anthropic
    - deepseek / openrouter → openai.OpenAI
    """
    provider = settings.llm_provider

    if provider == "openrouter":
        from openai import OpenAI
        return OpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )
    elif provider == "deepseek":
        from openai import OpenAI
        return OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
    else:
        import anthropic
        return anthropic.Anthropic()


def get_model(override: str | None = None) -> str:
    """获取当前 provider 对应的模型名"""
    if override:
        return override
    if settings.llm_provider == "deepseek":
        return settings.deepseek_model
    return settings.main_model


def get_light_model() -> str:
    """获取轻量模型名（DeepSeek 直连）"""
    return settings.light_model
