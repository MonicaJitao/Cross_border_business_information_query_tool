"""
火山引擎联网搜索 Provider。

API 文档：https://www.volcengine.com/docs/87772/2272953
Endpoint: POST https://open.feedcoopapi.com/search_api/web_search
认证：Authorization: Bearer <API_KEY>

请求体核心字段：
  Query:       搜索查询词
  SearchType:  "web" | "web_summary" | "image"
  Count:       返回条数（最多50条）
  Filter:      过滤条件（NeedUrl/NeedContent等）
  NeedSummary: 是否需要精准摘要

响应解析：使用 Result.WebResults 数组（每条含 Title / Url / Snippet / Summary）
"""
import asyncio
import logging
import time
from typing import Any, Optional

import httpx

from .base import SearchProvider, SearchResponse, SearchResult

logger = logging.getLogger(__name__)

VOLCENGINE_SEARCH_URL = "https://open.feedcoopapi.com/search_api/web_search"

_MIN_INTERVAL = 0.2      # 火山引擎接口至少间隔 0.2s（默认5 QPS）
_BACKOFF_BASE = 2.0
_BACKOFF_MAX  = 60.0


class VolcengineProvider(SearchProvider):
    def __init__(
        self,
        api_key: str,
        timeout: float = 20.0,
    ):
        self._api_key   = api_key
        self._timeout   = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._consecutive_failures = 0
        self._last_request_at: float = 0.0

    @property
    def name(self) -> str:
        return "volcengine"

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                trust_env=False,
            )
        return self._client

    async def _rate_wait(self) -> None:
        interval = min(
            _MIN_INTERVAL * (_BACKOFF_BASE ** min(self._consecutive_failures, 4)),
            _BACKOFF_MAX,
        )
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < interval:
            await asyncio.sleep(interval - elapsed)

    async def search(self, query: str, num_results: int = 10) -> SearchResponse:
        await self._rate_wait()

        payload: dict[str, Any] = {
            "Query": query,
            "SearchType": "web",
            "Count": min(num_results, 50),  # 火山引擎最多支持50条
            "Filter": {"NeedUrl": True},
            "NeedSummary": True,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        client = self._get_client()
        self._last_request_at = time.monotonic()

        try:
            resp = await client.post(VOLCENGINE_SEARCH_URL, json=payload, headers=headers)

            if resp.status_code == 429:
                self._consecutive_failures += 1
                retry_after = min(1.0 * (2 ** (self._consecutive_failures - 1)), 4.0)
                logger.warning("火山引擎 429，退避 %.1fs", retry_after)
                await asyncio.sleep(retry_after)
                return SearchResponse(query=query, error="rate_limited")

            if resp.status_code in (401, 403):
                return SearchResponse(query=query, error=f"volcengine_auth_error_{resp.status_code}")

            resp.raise_for_status()
            data = resp.json()
            self._consecutive_failures = 0

            raw_snapshot = _truncate_raw(data)
            logger.debug("火山引擎搜索 raw keys: %s", list(data.keys()) if isinstance(data, dict) else type(data).__name__)

            # 检查错误码
            error_info = _extract_error(data)
            if error_info:
                logger.warning("火山引擎搜索错误（query=%s）: %s", query[:40], error_info)
                return SearchResponse(query=query, error=error_info, raw_response=raw_snapshot)

            # 提取 WebResults 数组
            web_results = _extract_web_results(data)

            if not web_results:
                logger.warning("火山引擎搜索 200 但未解析到 WebResults（query=%s）keys=%s",
                               query[:40], list(data.keys()) if isinstance(data, dict) else "?")
                return SearchResponse(query=query, error="empty_results_payload", raw_response=raw_snapshot)

            results: list[SearchResult] = []
            for item in web_results:
                title   = str(item.get("Title", "")).strip()
                url     = str(item.get("Url", "")).strip()
                # 优先使用 Snippet，如果为空则使用 Summary
                snippet = str(item.get("Snippet", "") or item.get("Summary", "")).strip()
                source  = str(item.get("SiteName", "")).strip()
                pub_date = item.get("PublishTime")

                if not title and not url and not snippet:
                    continue
                results.append(SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source=source,
                    published_date=str(pub_date) if pub_date else None,
                    provider_name="volcengine",
                ))

            if not results:
                return SearchResponse(query=query, error="empty_results_payload", raw_response=raw_snapshot)

            return SearchResponse(query=query, results=results, raw_response=raw_snapshot)

        except httpx.TimeoutException:
            self._consecutive_failures += 1
            logger.warning("火山引擎搜索超时（query=%s）", query[:40])
            return SearchResponse(query=query, error="timeout")
        except Exception as exc:
            self._consecutive_failures += 1
            logger.exception("火山引擎搜索异常（query=%s）: %s", query[:40], exc)
            return SearchResponse(query=query, error=str(exc))

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


def _extract_error(data: Any) -> Optional[str]:
    """
    从火山引擎响应中提取错误信息。
    错误信息在 ResponseMetadata.Error 中。
    """
    if not isinstance(data, dict):
        return None

    # 检查 ResponseMetadata.Error
    metadata = data.get("ResponseMetadata")
    if isinstance(metadata, dict):
        error = metadata.get("Error")
        if isinstance(error, dict):
            code = error.get("CodeN") or error.get("Code")
            message = error.get("Message", "")
            if code:
                return f"volcengine_error_{code}:{message}".rstrip(":")

    return None


def _extract_web_results(data: Any) -> list[dict]:
    """
    从火山引擎响应中提取 WebResults 列表。
    支持多种响应结构：Result.WebResults、顶层 WebResults 等。
    """
    if not isinstance(data, dict):
        return []

    # 候选路径
    for path in [["Result", "WebResults"], ["WebResults"], ["data", "WebResults"]]:
        cur: Any = data
        for key in path:
            if isinstance(cur, dict):
                cur = cur.get(key)
            else:
                cur = None
                break
        if isinstance(cur, list) and cur and isinstance(cur[0], dict):
            return cur

    return []


def _truncate_raw(data: Any, max_len: int = 2000) -> dict:
    """截断原始响应，用于调试展示"""
    try:
        import json
        text = json.dumps(data, ensure_ascii=False, default=str)
        if len(text) <= max_len:
            return data if isinstance(data, dict) else {"_raw": text}
        return {"_truncated": text[:max_len] + "..."}
    except Exception:
        return {"_error": "无法序列化原始响应"}
