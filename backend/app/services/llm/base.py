from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMConfig:
    """用户传入的 LLM 配置（每次任务随 config JSON 传入，不落盘）"""
    provider: str                  # "claude_proxy" | "deepseek_official"
    base_url: str
    model: str
    api_key: Optional[str] = None  # 若为 None，由 Settings 中后端预置 key 填充


@dataclass
class LLMResponse:
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


class LLMProvider(ABC):
    """LLM 调用抽象接口"""

    @abstractmethod
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        ...

    async def close(self) -> None:
        pass
