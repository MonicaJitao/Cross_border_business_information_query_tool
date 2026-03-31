"""
抽取结果数据模型。

summary 和 tags 由原来的固定 Pydantic 子模型改为 dict[str, str]：
  - key = FieldDef.id
  - value = LLM 输出的字段值

这样新增/删除字段时只需修改字段目录（fields.py），无需改模型。
"""
from pydantic import BaseModel, Field
from typing import Any, Optional


class CompanyTrace(BaseModel):
    """每家公司的完整处理轨迹，用于前端可展开调试视图"""
    search_queries: list[str] = Field(default_factory=list)
    # 每次搜索的原始 API 响应（含 query 标签和来源 provider）
    search_raw_responses: list[dict[str, Any]] = Field(default_factory=list)
    # 去重后送给 LLM 的搜索结果摘要（title/url/snippet/provider_name）
    search_parsed_results: list[dict[str, str]] = Field(default_factory=list)
    llm_evidence_summary: Optional[str] = None   # 送给 LLM 的完整 prompt
    llm_raw_output: Optional[str] = None          # LLM 的原始文本输出
    final_result: Optional[dict[str, Any]] = None # 最终结构化结果（不含 trace 本身）


class CompanyExtraction(BaseModel):
    company_name: str
    # summary 字段结果，key = FieldDef.id（group="summary" 的字段）
    summary: dict[str, str] = Field(default_factory=dict)
    # summary 字段的 LLM 判断理由，key = FieldDef.id
    summary_notes: dict[str, str] = Field(default_factory=dict)
    # tags 字段结果，key = FieldDef.id（group="tags" 的字段）
    tags: dict[str, str] = Field(default_factory=dict)
    # tags 字段的 LLM 判断理由，key = FieldDef.id
    tags_notes: dict[str, str] = Field(default_factory=dict)
    evidence_count: int = 0
    sources: list[str] = Field(default_factory=list)
    error: Optional[str] = None
    trace: CompanyTrace = Field(default_factory=CompanyTrace)
