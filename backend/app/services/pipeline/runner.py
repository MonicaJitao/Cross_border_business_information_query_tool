"""
批处理 Pipeline Runner。

主要变更：
  - search_providers 改为 list[SearchProvider]（支持同时启用多个搜索源）
  - 每个 query 并行调用所有选中搜索源，结果按 URL 去重后合并（merge+dedup）
  - 新增 search_result_limit 参数，透传给各 provider 的 num_results
  - 新增 field_defs 参数，透传给 extract_company_info 动态构建 prompt
  - trace 中记录各 provider 的原始响应以及去重后的合并结果
"""
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from ..search.base import SearchProvider, SearchResponse, SearchResult
from ..llm.base import LLMProvider
from ..extract.extractor import extract_company_info
from ..extract.fields import FieldDef
from ..extract.schema import CompanyExtraction, CompanyTrace
from .keywords import build_keyword_groups, MIN_RESULTS_TO_SKIP

logger = logging.getLogger(__name__)


@dataclass
class ConcurrencyConfig:
    search: int = 5
    llm: int = 3


@dataclass
class ProgressEvent:
    event: str            # "start"|"company_done"|"company_error"|"log"|"done"
    total: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    company_name: str = ""
    message: str = ""
    elapsed_s: float = 0.0
    eta_s: Optional[float] = None
    detail: Optional[dict] = None


# ── 多搜索源聚合 ──────────────────────────────────────────────────────────

async def _multi_search(
    query: str,
    providers_with_limits: list[tuple[SearchProvider, int]],  # 改为元组列表
) -> tuple[list[SearchResult], list[dict]]:
    """
    并行调用所有搜索源，每个源使用独立的检索数量。
    对结果按 URL 去重后合并。

    Args:
        query: 搜索查询词
        providers_with_limits: (provider, num_results) 元组列表

    Returns:
        merged_results: 去重后的结果列表
        raw_response_entries: 每个 provider 的原始响应条目
    """
    tasks = [p.search(query, num_results=n) for p, n in providers_with_limits]
    responses: list[SearchResponse | BaseException] = await asyncio.gather(*tasks, return_exceptions=True)

    merged: list[SearchResult] = []
    raw_entries: list[dict] = []
    seen_urls: set[str] = set()
    seen_fps: set[str] = set()   # 无 URL 时的 title+snippet 指纹

    for (provider, _), resp in zip(providers_with_limits, responses):
        if isinstance(resp, BaseException):
            logger.warning("搜索源 %s 异常（query=%s）: %s", provider.name, query[:40], resp)
            continue

        if resp.raw_response:
            raw_entries.append({
                "query":         query,
                "provider_name": provider.name,
                "raw":           resp.raw_response,
            })

        if not resp.ok:
            continue

        for r in resp.results:
            if r.url:
                if r.url in seen_urls:
                    continue
                seen_urls.add(r.url)
            else:
                fp = f"{r.title[:60]}|{r.snippet[:60]}"
                if fp in seen_fps:
                    continue
                seen_fps.add(fp)
            merged.append(r)

    return merged, raw_entries


# ── 辅助函数 ──────────────────────────────────────────────────────────────

def _results_to_dicts(results: list[SearchResult]) -> list[dict[str, str]]:
    return [
        {
            "title":         r.title,
            "url":           r.url,
            "snippet":       r.snippet[:200],
            "provider_name": r.provider_name,
        }
        for r in results
    ]


def _truncate_str(s: str, max_len: int = 2000) -> str:
    return s[:max_len] + "..." if len(s) > max_len else s


# ── 主 Pipeline ───────────────────────────────────────────────────────────

async def run_pipeline(
    companies: list[str],
    search_providers: list[tuple[SearchProvider, int]],  # 改为 (provider, num_results) 元组
    llm_provider: LLMProvider,
    concurrency: ConcurrencyConfig,
    event_queue: asyncio.Queue,
    field_defs: list[FieldDef],
    # 移除 search_result_limit: int = 10 参数
    pre_results: Optional[list[Optional[CompanyExtraction]]] = None,
    cancel_event: Optional[asyncio.Event] = None,
) -> list[CompanyExtraction]:
    total = len(companies)
    results: list[Optional[CompanyExtraction]] = (
        list(pre_results) if pre_results else [None] * total
    )
    completed = 0
    failed = 0
    skipped = 0
    start_ts = time.monotonic()

    search_sem = asyncio.Semaphore(concurrency.search)
    llm_sem    = asyncio.Semaphore(concurrency.llm)

    pre_done = sum(1 for r in results if r is not None)
    provider_names = " + ".join(p.name for p, _ in search_providers) or "（无搜索源）"
    limits_info = ", ".join(f"{p.name}:{n}条" for p, n in search_providers)

    await event_queue.put(ProgressEvent(
        event="start", total=total,
        message=(
            f"开始处理 {total} 家企业"
            + (f"（续传 {pre_done} 家）" if pre_done else "")
            + f"  搜索源: {limits_info}"
        ),
    ))

    # 续传结果直接推送到前端列表
    if pre_done:
        for r in results:
            if r is not None:
                completed += 1
                await event_queue.put(ProgressEvent(
                    event="company_done",
                    total=total, completed=completed, failed=failed, skipped=skipped,
                    company_name=r.company_name,
                    message="续传：已有结果，跳过",
                    detail={"evidence_count": r.evidence_count, "sources": r.sources[:3], "resumed": True},
                ))

    async def process_one(idx: int, company: str) -> None:
        nonlocal completed, failed, skipped

        if results[idx] is not None:
            return

        try:
            if cancel_event and cancel_event.is_set():
                skipped += 1
                results[idx] = CompanyExtraction(company_name=company, error="已取消")
                await event_queue.put(ProgressEvent(
                    event="company_error",
                    total=total, completed=completed, failed=failed, skipped=skipped,
                    company_name=company, message="已取消（任务停止前未处理）",
                    elapsed_s=time.monotonic() - start_ts,
                ))
                return

            trace = CompanyTrace()

            # ── 搜索阶段 ────────────────────────────────────────────────
            await event_queue.put(ProgressEvent(
                event="log", total=total, completed=completed, failed=failed, skipped=skipped,
                company_name=company, message=f"[搜索] 开始: {company}",
            ))

            all_results: list[SearchResult] = []
            keyword_groups = build_keyword_groups(company)
            trace.search_queries = keyword_groups

            for group_query in keyword_groups:
                if cancel_event and cancel_event.is_set():
                    break
                async with search_sem:
                    merged, raw_entries = await _multi_search(
                        group_query, search_providers  # 直接传递 providers_with_limits
                    )

                trace.search_raw_responses.extend(raw_entries)

                if merged:
                    all_results.extend(merged)
                    await event_queue.put(ProgressEvent(
                        event="log", total=total, completed=completed, failed=failed, skipped=skipped,
                        company_name=company,
                        message=f"[搜索] {company} 累计 {len(all_results)} 条证据",
                    ))
                    if len(all_results) >= MIN_RESULTS_TO_SKIP:
                        break
                else:
                    await event_queue.put(ProgressEvent(
                        event="log", total=total, completed=completed, failed=failed, skipped=skipped,
                        company_name=company, message=f"[搜索] 关键词「{group_query[:30]}」无结果",
                    ))

            trace.search_parsed_results = _results_to_dicts(all_results)

            if cancel_event and cancel_event.is_set():
                skipped += 1
                results[idx] = CompanyExtraction(company_name=company, error="已取消", trace=trace)
                await event_queue.put(ProgressEvent(
                    event="company_error",
                    total=total, completed=completed, failed=failed, skipped=skipped,
                    company_name=company, message="已取消（搜索后停止）",
                    elapsed_s=time.monotonic() - start_ts,
                ))
                return

            # ── LLM 抽取阶段 ────────────────────────────────────────────
            await event_queue.put(ProgressEvent(
                event="log", total=total, completed=completed, failed=failed, skipped=skipped,
                company_name=company,
                message=f"[LLM] 开始抽取: {company}（{len(all_results)} 条证据）",
            ))

            async with llm_sem:
                extraction, user_prompt, llm_raw = await extract_company_info(
                    company, all_results, llm_provider, field_defs
                )

            trace.llm_evidence_summary = _truncate_str(user_prompt, 3000)
            trace.llm_raw_output       = _truncate_str(llm_raw, 3000)
            trace.final_result         = extraction.model_dump(exclude={"trace"})

            extraction.trace = trace
            results[idx] = extraction
            elapsed = time.monotonic() - start_ts

            if extraction.error:
                failed += 1
                await event_queue.put(ProgressEvent(
                    event="company_error",
                    total=total, completed=completed, failed=failed, skipped=skipped,
                    company_name=company, message=extraction.error,
                    elapsed_s=elapsed,
                    detail={"trace": _serialize_trace(trace)},
                ))
            else:
                completed += 1
                done_count = completed + failed + skipped
                eta = (elapsed / done_count) * (total - done_count) if done_count > 0 else None
                await event_queue.put(ProgressEvent(
                    event="company_done",
                    total=total, completed=completed, failed=failed, skipped=skipped,
                    company_name=company,
                    message=f"完成（证据 {extraction.evidence_count} 条）",
                    elapsed_s=elapsed,
                    eta_s=eta,
                    detail={
                        "evidence_count": extraction.evidence_count,
                        "sources":        extraction.sources[:3],
                        "trace":          _serialize_trace(trace),
                    },
                ))

        except Exception as exc:
            failed += 1
            logger.exception("process_one 内部异常（公司: %s）", company)
            err_msg = f"{type(exc).__name__}: {exc}"
            results[idx] = CompanyExtraction(company_name=company, error=f"内部异常: {err_msg}")
            await event_queue.put(ProgressEvent(
                event="company_error",
                total=total, completed=completed, failed=failed, skipped=skipped,
                company_name=company, message=f"内部异常: {err_msg}",
                elapsed_s=time.monotonic() - start_ts,
            ))

    tasks = [
        asyncio.create_task(process_one(i, c))
        for i, c in enumerate(companies)
        if results[i] is None
    ]
    gather_res = await asyncio.gather(*tasks, return_exceptions=True)

    for res in gather_res:
        if isinstance(res, Exception):
            logger.error("gather 层异常: %r", res)

    cancelled   = cancel_event and cancel_event.is_set()
    finish_msg  = "已停止（部分完成）" if cancelled else f"全部完成。成功 {completed}，失败 {failed}"

    await event_queue.put(ProgressEvent(
        event="done",
        total=total, completed=completed, failed=failed, skipped=skipped,
        elapsed_s=time.monotonic() - start_ts,
        message=finish_msg,
    ))

    return [r or CompanyExtraction(company_name=companies[i], error="未处理") for i, r in enumerate(results)]


def _serialize_trace(trace: CompanyTrace) -> dict[str, Any]:
    """将 trace 序列化为可 JSON 化的 dict，控制大小"""
    return {
        "search_queries":        trace.search_queries,
        "search_raw_responses":  trace.search_raw_responses[:6],
        "search_parsed_results": trace.search_parsed_results[:20],
        "llm_evidence_summary":  _truncate_str(trace.llm_evidence_summary or "", 2000),
        "llm_raw_output":        _truncate_str(trace.llm_raw_output or "", 2000),
        "final_result":          trace.final_result,
    }
