from .anthropic_compat import AnthropicCompatProvider
from .base import LLMConfig, LLMProvider
from .openai_compat import OpenAICompatProvider
from ...core.config import settings


def build_llm_provider(cfg: LLMConfig) -> LLMProvider:
    """根据用户传入的 LLMConfig 构建 Provider 实例。
    若 api_key 为空，则从后端预置配置中取。
    """
    if cfg.provider == "claude_proxy":
        key = cfg.api_key or settings.claude_proxy_api_key
        url = cfg.base_url or settings.claude_proxy_base_url or ""
        model = cfg.model or settings.claude_proxy_default_model
    elif cfg.provider == "deepseek_official":
        key = cfg.api_key or settings.deepseek_api_key
        url = cfg.base_url or settings.deepseek_base_url
        model = cfg.model or settings.deepseek_default_model
    else:
        raise ValueError(f"未知 LLM provider: {cfg.provider}")

    if not key:
        raise ValueError(f"未提供 API Key 且后端无预置 Key（provider={cfg.provider}）")
    if not url:
        raise ValueError(f"未提供 base_url（provider={cfg.provider}）")

    if cfg.provider == "claude_proxy":
        return AnthropicCompatProvider(base_url=url, api_key=key, model=model)
    return OpenAICompatProvider(base_url=url, api_key=key, model=model)
