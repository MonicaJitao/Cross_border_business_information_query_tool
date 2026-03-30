"""
OpenAI-compatible LLM client.
DeepSeek 官方与 Claude 中转站均使用 OpenAI Chat Completions 格式，
统一用此 client 接入。
"""
import logging
from typing import Optional

import httpx

from .base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class OpenAICompatProvider(LLMProvider):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=self._timeout,
                # 与搜索客户端保持一致，避免外部 SSL_CERT_FILE / 代理环境变量
                # 指向不存在文件时让整个任务批量失败。
                trust_env=False,
            )
        return self._client

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        client = self._get_client()
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            resp = await client.post("/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            return LLMResponse(
                content=choice,
                model=data.get("model", self._model),
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            )
        except httpx.TimeoutException:
            logger.warning("LLM 请求超时（model=%s）", self._model)
            return LLMResponse(content="", model=self._model, error="timeout")
        except Exception as exc:
            logger.exception("LLM 请求异常: %s", exc)
            return LLMResponse(content="", model=self._model, error=str(exc))

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
