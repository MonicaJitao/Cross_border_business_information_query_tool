"""
百度千帆搜索 Provider。

API 文档：https://cloud.baidu.com/doc/qianfan-api/s/Wmbq4z7e5
Endpoint: POST https://qianfan.baidubce.com/v2/ai_search/web_search
认证：Authorization: Bearer <API_KEY>

请求体核心字段：
  messages:               [{"role": "user", "content": query}]
  search_source:          "baidu_search_v2"
  resource_type_filter:   [{"type": "web", "top_k": N}]

响应解析：使用 references 数组（每条含 title / url / content / date）
"""
import logging
from typing import Any, Optional

import httpx

from .base import (
    AsyncRateLimiter,
    SearchProvider, SearchResponse, SearchResult,
    extract_first_list, retry_with_backoff, truncate_raw,
)

logger = logging.getLogger(__name__)

BAIDU_SEARCH_URL = "https://qianfan.baidubce.com/v2/ai_search/web_search"

_MIN_INTERVAL = 0.2
_MAX_RETRIES = 3

_CANDIDATE_PATHS: list[list[str]] = [
    ["references"],
    ["data", "references"],
    ["search_results"],
    ["data", "search_results"],
]


class BaiduQianfanProvider(SearchProvider):
    def __init__(
        self,
        api_key: str,
        timeout: float = 20.0,
    ):
        self._api_key = api_key
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._consecutive_failures = 0
        self._limiter = AsyncRateLimiter(_MIN_INTERVAL)

    @property
    def name(self) -> str:
        return "baidu"

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                trust_env=False,
            )
        return self._client

    async def search(self, query: str, num_results: int = 10) -> SearchResponse:
        async def _attempt() -> SearchResponse:
            return await self._do_search(query, num_results)

        return await retry_with_backoff(
            _attempt, query, max_retries=_MAX_RETRIES, log=logger
        )

    async def _do_search(self, query: str, num_results: int) -> SearchResponse:
        await self._limiter.acquire(self._consecutive_failures)

        payload: dict[str, Any] = {
            "messages": [{"role": "user", "content": query}],
            "search_source": "baidu_search_v2",
            "resource_type_filter": [{"type": "web", "top_k": num_results}],
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        client = self._get_client()

        try:
            resp = await client.post(BAIDU_SEARCH_URL, json=payload, headers=headers)

            if resp.status_code == 429:
                self._consecutive_failures += 1
                logger.warning("百度（429，连续失败 %d 次）", self._consecutive_failures)
                return SearchResponse(query=query, error="rate_limited")

            if resp.status_code in (401, 403):
                return SearchResponse(query=query, error=f"baidu_auth_error_{resp.status_code}")

            resp.raise_for_status()
            data = resp.json()
            self._consecutive_failures = 0

            raw_snapshot = truncate_raw(data)
            logger.debug("百度搜索 raw keys: %s", list(data.keys()) if isinstance(data, dict) else type(data).__name__)

            references = extract_first_list(data, _CANDIDATE_PATHS, fallback_scan=False)

            if not references:
                logger.warning("百度搜索 200 但未解析到 references（query=%s）keys=%s",
                               query[:40], list(data.keys()) if isinstance(data, dict) else "?")
                return SearchResponse(query=query, error="empty_results_payload", raw_response=raw_snapshot)

            results: list[SearchResult] = []
            for ref in references:
                title   = str(ref.get("title", "")).strip()
                url     = str(ref.get("url", "")).strip()
                snippet = str(ref.get("content", "") or ref.get("snippet", "")).strip()
                pub_date = ref.get("date") or ref.get("publish_time")

                if not title and not url and not snippet:
                    continue
                results.append(SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    published_date=str(pub_date) if pub_date else None,
                    provider_name="baidu",
                ))

            if not results:
                return SearchResponse(query=query, error="empty_results_payload", raw_response=raw_snapshot)

            return SearchResponse(query=query, results=results, raw_response=raw_snapshot)

        except httpx.TimeoutException:
            self._consecutive_failures += 1
            logger.warning("百度搜索超时（query=%s）", query[:40])
            return SearchResponse(query=query, error="timeout")
        except Exception as exc:
            self._consecutive_failures += 1
            logger.exception("百度搜索异常（query=%s）: %s", query[:40], exc)
            return SearchResponse(query=query, error=str(exc))

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
