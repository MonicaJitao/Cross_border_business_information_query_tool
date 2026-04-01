"""
LLM 抽取编排层。

接受已去重的 SearchResult 列表和本次任务的 field_defs，
调用 LLM，解析 JSON 输出，映射到 CompanyExtraction。
"""
import logging
from ..llm.base import LLMProvider
from ..search.base import SearchResult
from .fields import FieldDef
from .schema import CompanyExtraction
from .prompt import SYSTEM_PROMPT, build_user_prompt
from .parse import parse_llm_json

logger = logging.getLogger(__name__)


def _build_evidence_snippets(results: list[SearchResult]) -> list[str]:
    """将 SearchResult 列表转为 prompt 用的文本片段"""
    snippets = []
    for r in results:
        parts = []
        if r.title:
            parts.append(f"标题：{r.title}")
        if r.url:
            parts.append(f"来源：{r.url}")
        if r.snippet:
            parts.append(f"摘要：{r.snippet}")
        if r.provider_name:
            parts.append(f"搜索源：{r.provider_name}")
        if parts:
            snippets.append("\n".join(parts))
    return snippets


async def extract_company_info(
    company_name: str,
    search_results: list[SearchResult],
    llm: LLMProvider,
    field_defs: list[FieldDef],
) -> tuple[CompanyExtraction, str, str]:
    """
    Returns: (extraction, user_prompt_sent, llm_raw_output)

    summary 和 tags 均为 dict[str, str]，key 为 field.id。
    未选中字段不出现在输出 dict 中。
    """
    snippets = _build_evidence_snippets(search_results)
    user_prompt = build_user_prompt(company_name, snippets, field_defs)

    llm_resp = await llm.complete(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )
    raw_output = llm_resp.content or ""

    if not llm_resp.ok:
        return (
            CompanyExtraction(
                company_name=company_name,
                evidence_count=len(search_results),
                sources=[r.url for r in search_results[:5] if r.url],
                error=f"LLM 错误: {llm_resp.error}",
            ),
            user_prompt,
            raw_output,
        )

    parsed, strategy = parse_llm_json(raw_output)
    if parsed is None:
        return (
            CompanyExtraction(
                company_name=company_name,
                evidence_count=len(search_results),
                sources=[r.url for r in search_results[:5] if r.url],
                error="JSON 解析失败",
            ),
            user_prompt,
            raw_output,
        )

    logger.debug("JSON 解析策略: %s（公司: %s）", strategy, company_name)

    summary_data: dict = parsed.get("summary", {})
    tags_data: dict    = parsed.get("tags", {})
    summary_notes_data: dict = parsed.get("summary_notes", {})
    tags_notes_data: dict    = parsed.get("tags_notes", {})

    # 只保留本次选中字段的值，其余忽略
    summary: dict[str, str] = {}
    tags: dict[str, str]    = {}
    summary_notes: dict[str, str] = {}
    tags_notes: dict[str, str]    = {}

    for fd in field_defs:
        if fd.group == "summary":
            val = summary_data.get(fd.id)
            summary[fd.id] = str(val).strip() if val is not None else ""
            note_val = summary_notes_data.get(fd.id)
            summary_notes[fd.id] = str(note_val).strip() if note_val is not None else ""
        else:
            val = tags_data.get(fd.id)
            tags[fd.id] = str(val).strip() if val is not None else ""
            note_val = tags_notes_data.get(fd.id)
            tags_notes[fd.id] = str(note_val).strip() if note_val is not None else ""

    extraction = CompanyExtraction(
        company_name=company_name,
        summary=summary,
        tags=tags,
        summary_notes=summary_notes,
        tags_notes=tags_notes,
        evidence_count=len(search_results),
        sources=[r.url for r in search_results[:5] if r.url],
    )
    return extraction, user_prompt, raw_output
