"""
秘塔 AI 搜索 Provider
API: https://metaso.cn/search-api/playground
"""
import asyncio
import json
import logging
import time
from typing import Any, Optional

import httpx

from .base import SearchProvider, SearchResponse, SearchResult

logger = logging.getLogger(__name__)

METASO_SEARCH_URL = "https://metaso.cn/api/v1/search"

_MIN_INTERVAL = 0.1
_BACKOFF_BASE = 2.0
_BACKOFF_MAX  = 60.0

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


def _dig(data: dict, path: list[str]) -> Any:
    cur = data
    for key in path:
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            return None
    return cur


def _extract_items(data: dict) -> list[dict]:
    for path in _CANDIDATE_PATHS:
        candidate = _dig(data, path)
        if isinstance(candidate, list) and len(candidate) > 0:
            if isinstance(candidate[0], dict):
                logger.info("秘塔结果路径命中: %s (%d 条)", ".".join(path), len(candidate))
                return candidate
    # 兜底：扫描顶层所有 list[dict] 字段，避免字段名再次变化时整批变成 0 条证据
    for key, candidate in data.items():
        if isinstance(candidate, list) and len(candidate) > 0 and isinstance(candidate[0], dict):
            logger.info("秘塔结果路径兜底命中: %s (%d 条)", key, len(candidate))
            return candidate
    return []


class MetasoProvider(SearchProvider):
    def __init__(
        self,
        api_key: str,
        # metaso 文档 scope 示例为 webpage/document/scholar/...
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
        self._last_request_at: float = 0.0

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

    async def _rate_wait(self) -> None:
        interval = min(_MIN_INTERVAL * (_BACKOFF_BASE ** min(self._consecutive_failures, 4)), _BACKOFF_MAX)
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < interval:
            await asyncio.sleep(interval - elapsed)

    async def search(self, query: str, num_results: int = 0) -> SearchResponse:
        await self._rate_wait()
        n = num_results or self._num_results
        headers = {"Authorization": f"Bearer {self._api_key}"}
        # metaso /api/v1/search：q/scope/includeSummary 必填；size/page 二选一（示例用 size）
        payload = {"q": query, "scope": self._scope, "includeSummary": True, "size": n}
        client  = self._get_client()
        self._last_request_at = time.monotonic()

        try:
            resp = await client.post(METASO_SEARCH_URL, json=payload, headers=headers)

            if resp.status_code == 429:
                self._consecutive_failures += 1
                retry_after = min(1.0 * (2 ** (self._consecutive_failures - 1)), 4.0)
                logger.warning("Metaso 429，退避 %.1fs（连续失败 %d 次）", retry_after, self._consecutive_failures)
                await asyncio.sleep(retry_after)
                return SearchResponse(query=query, error="rate_limited")

            resp.raise_for_status()
            data = resp.json()
            self._consecutive_failures = 0

            raw_snapshot = _truncate_raw(data)
            logger.debug("Metaso raw keys: %s", list(data.keys()) if isinstance(data, dict) else type(data).__name__)

            if not isinstance(data, dict):
                return SearchResponse(
                    query=query,
                    error=f"unexpected_response_type: {type(data).__name__}",
                    raw_response={"_raw_type": str(type(data))},
                )

            # metaso 常见失败结构：{errCode:int, errMsg:str}
            err_code = data.get("errCode")
            if isinstance(err_code, int) and err_code != 0:
                err_msg = data.get("errMsg")
                err_msg_s = err_msg if isinstance(err_msg, str) else ""
                return SearchResponse(
                    query=query,
                    error=f"metaso_err_{err_code}:{err_msg_s}".rstrip(":"),
                    raw_response=raw_snapshot,
                )

            items = _extract_items(data)

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
                source = item.get("source", "")
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


def _truncate_raw(data: Any, max_str_len: int = 300) -> dict:
    """对原始响应做受控截断，用于调试和前端展示。"""
    try:
        text = json.dumps(data, ensure_ascii=False, default=str)
        if len(text) <= 2000:
            return data if isinstance(data, dict) else {"_raw": text}
        return {"_truncated": text[:2000] + "..."}
    except Exception:
        return {"_error": "无法序列化原始响应"}
