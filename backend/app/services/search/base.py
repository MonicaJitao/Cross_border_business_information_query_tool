from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


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
