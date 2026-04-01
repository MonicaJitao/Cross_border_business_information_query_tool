"""
秘塔 AI 搜索 Provider
API: https://metaso.cn/search-api/playground
"""
import json
import logging
from typing import Optional

import httpx

from .base import (
    AsyncRateLimiter,
    SearchProvider, SearchResponse, SearchResult,
    extract_first_list, retry_with_backoff, truncate_raw,
)

logger = logging.getLogger(__name__)

METASO_SEARCH_URL = "https://metaso.cn/api/v1/search"

_MIN_INTERVAL = 0.1
_MAX_RETRIES = 3

# 秘塔支持多种内容类型，候选路径比其他 Provider 更多；
# 同时启用兜底扫描（fallback_scan=True），容忍接口字段名随版本变更。
_CANDIDATE_PATHS: list[list[str]] = [
    ["results"],
    ["data", "results"],
    ["items"],
    ["data", "items"],
    ["webpages"],
    ["webPages", "value"],
    ["documents"],
    ["scholars"],
    ["podcasts"],
    ["videos"],
    ["images"],
    ["data"],
]


class MetasoProvider(SearchProvider):
    def __init__(
        self,
        api_key: str,
        scope: str = "webpage",
        num_results: int = 10,
        timeout: float = 15.0,
    ):
        self._api_key     = api_key
        self._scope       = scope
        self._num_results = num_results
        self._timeout     = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._consecutive_failures = 0
        self._limiter = AsyncRateLimiter(_MIN_INTERVAL)

    @property
    def name(self) -> str:
        return "metaso"

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                trust_env=False,
            )
        return self._client

    async def search(self, query: str, num_results: int = 0) -> SearchResponse:
        n = num_results or self._num_results

        async def _attempt() -> SearchResponse:
            return await self._do_search(query, n)

        return await retry_with_backoff(
            _attempt, query, max_retries=_MAX_RETRIES, log=logger
        )

    async def _do_search(self, query: str, num_results: int) -> SearchResponse:
        await self._limiter.acquire(self._consecutive_failures)

        headers = {"Authorization": f"Bearer {self._api_key}"}
        payload = {"q": query, "scope": self._scope, "includeSummary": True, "size": num_results}
        client  = self._get_client()

        try:
            resp = await client.post(METASO_SEARCH_URL, json=payload, headers=headers)

            if resp.status_code == 429:
                self._consecutive_failures += 1
                logger.warning("Metaso 429（连续失败 %d 次）", self._consecutive_failures)
                return SearchResponse(query=query, error="rate_limited")

            resp.raise_for_status()
            data = resp.json()
            self._consecutive_failures = 0

            raw_snapshot = truncate_raw(data)
            logger.debug("Metaso raw keys: %s", list(data.keys()) if isinstance(data, dict) else type(data).__name__)

            if not isinstance(data, dict):
                return SearchResponse(
                    query=query,
                    error=f"unexpected_response_type: {type(data).__name__}",
                    raw_response={"_raw_type": str(type(data))},
                )

            err_code = data.get("errCode")
            if isinstance(err_code, int) and err_code != 0:
                err_msg = data.get("errMsg")
                err_msg_s = err_msg if isinstance(err_msg, str) else ""
                return SearchResponse(
                    query=query,
                    error=f"metaso_err_{err_code}:{err_msg_s}".rstrip(":"),
                    raw_response=raw_snapshot,
                )

            items = extract_first_list(data, _CANDIDATE_PATHS, fallback_scan=True)

            if not items:
                logger.warning(
                    "Metaso 200 但未解析到结果 (query=%s)，顶层 keys=%s，前 500 字=%s",
                    query[:40], list(data.keys()), json.dumps(data, ensure_ascii=False)[:500],
                )
                return SearchResponse(
                    query=query,
                    error="empty_results_payload",
                    raw_response=raw_snapshot,
                )

            results: list[SearchResult] = []
            for item in items:
                title = (
                    item.get("title")
                    or item.get("name")
                    or ""
                )
                url = (
                    item.get("url")
                    or item.get("link")
                    or item.get("href")
                    or ""
                )
                snippet = (
                    item.get("snippet")
                    or item.get("content")
                    or item.get("description")
                    or item.get("abstract")
                    or ""
                )
                source   = item.get("source", "")
                pub_date = item.get("date") or item.get("published_date") or item.get("publishedDate")

                if not title and not url and not snippet:
                    continue
                results.append(SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source=source,
                    published_date=pub_date,
                    provider_name="metaso",
                ))

            if not results:
                return SearchResponse(
                    query=query,
                    error="empty_results_payload",
                    raw_response=raw_snapshot,
                )

            return SearchResponse(query=query, results=results, raw_response=raw_snapshot)

        except httpx.TimeoutException:
            self._consecutive_failures += 1
            logger.warning("Metaso 超时（query=%s）", query[:40])
            return SearchResponse(query=query, error="timeout")
        except Exception as exc:
            self._consecutive_failures += 1
            logger.exception("Metaso 异常（query=%s）: %s", query[:40], exc)
            return SearchResponse(query=query, error=str(exc))

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
