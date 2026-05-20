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
    timeout_sec = settings.llm_timeout

    if provider == "openrouter":
        from openai import AsyncOpenAI
        import httpx
        return AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            timeout=httpx.Timeout(timeout_sec, connect=10.0),
        )
    elif provider == "deepseek":
        from openai import AsyncOpenAI
        import httpx
        return AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            timeout=httpx.Timeout(timeout_sec, connect=10.0),
        )
    else:
        import anthropic
        import httpx
        return anthropic.AsyncAnthropic(
            timeout=httpx.Timeout(timeout_sec, connect=10.0),
        )


def get_light_client():
    """获取轻量模型的异步客户端——始终走 DeepSeek 官方直连"""
    from openai import AsyncOpenAI
    import httpx
    return AsyncOpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        timeout=httpx.Timeout(settings.llm_timeout, connect=10.0),
    )


def get_sync_client():
    """
    获取同步 LLM 客户端。
    - anthropic → anthropic.Anthropic
    - deepseek / openrouter → openai.OpenAI
    """
    provider = settings.llm_provider
    timeout_sec = settings.llm_timeout

    if provider == "openrouter":
        from openai import OpenAI
        import httpx
        return OpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            timeout=httpx.Timeout(timeout_sec, connect=10.0),
        )
    elif provider == "deepseek":
        from openai import OpenAI
        import httpx
        return OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            timeout=httpx.Timeout(timeout_sec, connect=10.0),
        )
    else:
        import anthropic
        import httpx
        return anthropic.Anthropic(
            timeout=httpx.Timeout(timeout_sec, connect=10.0),
        )


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


def get_deepseek_extra_body() -> dict:
    """DeepSeek 推理模型 (v4-flash) 非思考模式参数。

    思考模式下每轮 tool_use 累积 thinking token，3 轮工具循环可达 13.6s。
    文档：https://api-docs.deepseek.com/zh-cn/guides/thinking_mode
    """
    return {"thinking": {"type": "disabled"}}
