"""
Anthropic Messages API compatible LLM client.
用于 Claude 等走 Anthropic 格式的中转（如 POST /v1/messages）。
"""
import logging
from typing import Optional

import httpx

from .base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class AnthropicCompatProvider(LLMProvider):
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
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                timeout=self._timeout,
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
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "temperature": temperature,
        }
        try:
            resp = await client.post("/v1/messages", json=payload)
            resp.raise_for_status()
            data = resp.json()
            text = data["content"][0]["text"]
            usage = data.get("usage", {})
            return LLMResponse(
                content=text,
                model=data.get("model", self._model),
                prompt_tokens=usage.get("input_tokens", 0),
                completion_tokens=usage.get("output_tokens", 0),
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
