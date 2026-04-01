import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

_BACKOFF_BASE = 2.0
_BACKOFF_MAX = 60.0


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str = ""
    published_date: Optional[str] = None
    provider_name: str = ""   # 来源 provider，如 "metaso" 或 "baidu"


@dataclass
class SearchResponse:
    query: str
    results: list[SearchResult] = field(default_factory=list)
    error: Optional[str] = None
    raw_response: Optional[dict[str, Any]] = None

    @property
    def ok(self) -> bool:
        return self.error is None and len(self.results) > 0


class SearchProvider(ABC):
    """搜索源抽象接口，所有 Provider 必须实现此协议"""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    async def search(self, query: str, num_results: int = 10) -> SearchResponse:
        """执行搜索，返回结构化结果列表"""
        ...

    async def close(self) -> None:
        """释放资源（httpx session 等），默认无操作"""
        pass


# ---------------------------------------------------------------------------
# 共享工具：限流器
# ---------------------------------------------------------------------------

class AsyncRateLimiter:
    """
    基于槽位预留（slot reservation）的异步限流器。

    设计要点：asyncio.Lock 仅保护槽位的读-算-写三步（微秒级），
    sleep 在锁外执行。这样多个协程可真正并发执行网络 I/O，
    同时严格保证相邻两次发包之间的间隔不低于 min_interval（叠加退避时更长）。
    """

    def __init__(self, min_interval: float) -> None:
        self._min_interval = min_interval
        self._last_slot_at: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self, backoff_failures: int = 0) -> None:
        """占用一个发包槽位，若需要等待则在锁外 sleep。"""
        interval = min(
            self._min_interval * (_BACKOFF_BASE ** min(backoff_failures, 4)),
            _BACKOFF_MAX,
        )
        async with self._lock:
            now = time.monotonic()
            next_slot = self._last_slot_at + interval
            wait = next_slot - now
            # 预留槽位：无论是否需要等待，先把时间戳推进到该槽位
            self._last_slot_at = max(now, next_slot)

        if wait > 0:
            await asyncio.sleep(wait)


# ---------------------------------------------------------------------------
# 共享工具：通用重试
# ---------------------------------------------------------------------------

async def retry_with_backoff(
    fn: Callable[[], Awaitable[SearchResponse]],
    query: str,
    max_retries: int = 3,
    is_retriable: Optional[Callable[[SearchResponse], bool]] = None,
    log: Optional[logging.Logger] = None,
) -> SearchResponse:
    """
    通用指数退避重试包装器。

    当 is_retriable(result) 返回 True 时重试，最多重试 max_retries 次。
    默认将 error 中包含 "rate_limited" 或 "700429" 的响应视为可重试。
    """
    _log = log or logger

    def _default_retriable(r: SearchResponse) -> bool:
        if r.error is None:
            return False
        return "rate_limited" in r.error or "700429" in r.error

    check = is_retriable or _default_retriable
    result = SearchResponse(query=query, error="not_started")

    for attempt in range(max_retries + 1):
        result = await fn()
        if not check(result):
            return result
        if attempt < max_retries:
            wait = min(1.0 * (2 ** attempt), 8.0)
            _log.warning(
                "搜索限流，第 %d/%d 次重试，退避 %.1fs（query=%s）",
                attempt + 1, max_retries, wait, query[:40],
            )
            await asyncio.sleep(wait)

    _log.error("搜索限流重试耗尽（query=%s）", query[:40])
    return result


# ---------------------------------------------------------------------------
# 共享工具：防御性 JSON 提取
# ---------------------------------------------------------------------------

def dig_path(data: Any, path: list[str]) -> Any:
    """沿路径逐层提取嵌套字典值，任意层级类型不匹配时返回 None。"""
    cur = data
    for key in path:
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            return None
    return cur


def extract_first_list(
    data: dict,
    candidate_paths: list[list[str]],
    fallback_scan: bool = True,
) -> list[dict]:
    """
    按候选路径顺序提取首个非空 list[dict]。

    fallback_scan=True 时，若所有路径均未命中，则扫描顶层全部字段兜底，
    避免接口字段名变更后整批结果丢失。
    """
    for path in candidate_paths:
        candidate = dig_path(data, path)
        if isinstance(candidate, list) and candidate and isinstance(candidate[0], dict):
            return candidate
    if fallback_scan and isinstance(data, dict):
        for candidate in data.values():
            if isinstance(candidate, list) and candidate and isinstance(candidate[0], dict):
                return candidate
    return []


def truncate_raw(data: Any, max_len: int = 2000) -> dict:
    """截断原始响应至 max_len 字符，用于调试展示。"""
    try:
        text = json.dumps(data, ensure_ascii=False, default=str)
        if len(text) <= max_len:
            return data if isinstance(data, dict) else {"_raw": text}
        return {"_truncated": text[:max_len] + "..."}
    except Exception:
        return {"_error": "无法序列化原始响应"}
