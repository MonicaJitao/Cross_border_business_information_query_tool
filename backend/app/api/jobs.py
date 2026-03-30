"""
任务 API：上传、创建、SSE 进度、停止、下载
"""
import asyncio
import io
import json
import logging
from typing import Optional

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from ..core.config import settings
from ..services.extract.fields import ALL_BUILTIN_FIELDS, FieldDef
from ..services.extract.schema import CompanyExtraction
from ..services.llm.base import LLMConfig
from ..services.llm.factory import build_llm_provider
from ..services.pipeline.runner import ConcurrencyConfig, run_pipeline
from ..services.search.metaso import MetasoProvider
from ..services.search.baidu_qianfan import BaiduQianfanProvider
from ..services.search.base import SearchProvider
from ..services.storage.job_store import (
    JobStatus,
    build_result_excel,
    cancel_job,
    create_job,
    get_job,
)

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


# ── 请求 Schema ──────────────────────────────────────────────────

class LLMConfigIn(BaseModel):
    provider: str = "deepseek_official"
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None


class ConcurrencyConfigIn(BaseModel):
    search: int = Field(default=5, ge=1, le=20)
    llm: int = Field(default=3, ge=1, le=10)


class FieldDefIn(BaseModel):
    """前端提交的字段定义（内置字段 + 用户自定义字段共用此结构）"""
    id: str
    label: str
    group: str        # "summary" | "tags"
    col_name: str
    instruction: str
    field_type: str   # "yesno" | "text" | "region" | "amount"

    def to_field_def(self) -> FieldDef:
        return FieldDef(
            id=self.id,
            label=self.label,
            group=self.group,
            col_name=self.col_name,
            instruction=self.instruction,
            field_type=self.field_type,
        )


class JobConfig(BaseModel):
    # 搜索源：可单选或多选，如 ["metaso"] 或 ["metaso", "baidu"]
    search_providers: list[str] = Field(default_factory=lambda: ["metaso"])
    metaso_api_key: Optional[str] = None
    baidu_api_key: Optional[str] = None
    search_result_limit: int = Field(default=10, ge=1, le=50)
    # 字段定义：None 表示使用全部内置字段
    field_defs: Optional[list[FieldDefIn]] = None
    llm: LLMConfigIn = Field(default_factory=LLMConfigIn)
    concurrency: ConcurrencyConfigIn = Field(default_factory=ConcurrencyConfigIn)


# ── Excel 工具函数 ────────────────────────────────────────────────

def _pick_company_column(df: pd.DataFrame) -> int:
    """推断企业名称所在列索引"""
    if df.empty or df.shape[1] == 0:
        return 0
    name_keywords = ("企业", "公司", "名称", "单位", "主体", "客户")
    for i, col in enumerate(df.columns):
        if any(k in str(col) for k in name_keywords):
            return i
    # 退而求其次：选非数字内容最多的列
    best_idx, best_score = 0, -1
    for i in range(df.shape[1]):
        score = sum(
            1 for v in df.iloc[:, i].dropna().astype(str)
            if v.strip() and not v.strip().replace(".", "", 1).isdigit() and len(v.strip()) >= 2
        )
        if score > best_score:
            best_score, best_idx = score, i
    return best_idx


def _parse_resume_data(
    df: pd.DataFrame,
    company_col: int,
    field_defs: list[FieldDef],
) -> tuple[list[str], list[Optional[CompanyExtraction]]]:
    """
    从历史结果 Excel 中恢复已处理记录。
    判断是否已处理：任意选定字段的 col_name 在 df 列中，且值非空，且无错误记录。
    """
    df_cols = {str(c) for c in df.columns}
    # 与当前 field_defs 匹配的列名集合（用于判断是否是结果文件）
    matching_col_names = [fd.col_name for fd in field_defs if fd.col_name in df_cols]
    has_result_cols = bool(matching_col_names)

    companies: list[str] = []
    pre_results: list[Optional[CompanyExtraction]] = []

    for _, row in df.iterrows():
        raw_name = row.iloc[company_col]
        name = "" if pd.isna(raw_name) else str(raw_name).strip()
        if not name:
            continue
        companies.append(name)

        if not has_result_cols:
            pre_results.append(None)
            continue

        # 检查是否已处理：至少一个字段有值且无错误
        error_val = row.get("错误信息", "")
        error_str = "" if pd.isna(error_val) else str(error_val).strip()

        def _get(col: str) -> str:
            v = row.get(col, "")
            return "" if pd.isna(v) else str(v).strip()

        any_filled = any(_get(cn) for cn in matching_col_names)

        if any_filled and not error_str:
            summary: dict[str, str] = {}
            tags: dict[str, str] = {}
            for fd in field_defs:
                val = _get(fd.col_name)
                if fd.group == "summary":
                    summary[fd.id] = val
                else:
                    tags[fd.id] = val

            ev_raw = row.get("证据条数", 0)
            evidence_count = 0 if pd.isna(ev_raw) else int(ev_raw)
            src_raw = row.get("来源URL", "")
            sources = [] if pd.isna(src_raw) else [u.strip() for u in str(src_raw).split("|") if u.strip()]

            pre_results.append(CompanyExtraction(
                company_name=name,
                summary=summary,
                tags=tags,
                evidence_count=evidence_count,
                sources=sources,
            ))
        else:
            pre_results.append(None)

    return companies, pre_results


# ── GET /api/meta ─────────────────────────────────────────────────

@router.get("/meta")
async def get_meta():
    """
    返回前端初始化所需的元信息：
    - 搜索源列表（含后端是否预置了 API Key）
    - LLM 列表
    - 字段目录（全量内置字段，前端据此渲染字段选择面板）
    """
    return {
        "search_providers": [
            {
                "id":             "metaso",
                "name":           "秘塔AI搜索",
                "has_preset_key": bool(settings.metaso_api_key),
            },
            {
                "id":             "baidu",
                "name":           "百度千帆搜索",
                "has_preset_key": bool(settings.baidu_api_key),
            },
        ],
        "llm_providers": [
            {
                "id":               "claude_proxy",
                "name":             "Claude（中转站）",
                "has_preset_key":   bool(settings.claude_proxy_api_key),
                "default_base_url": settings.claude_proxy_base_url or "",
                "default_model":    settings.claude_proxy_default_model,
            },
            {
                "id":               "deepseek_official",
                "name":             "DeepSeek（官方）",
                "has_preset_key":   bool(settings.deepseek_api_key),
                "default_base_url": settings.deepseek_base_url,
                "default_model":    settings.deepseek_default_model,
            },
        ],
        # 字段目录：前端用于渲染字段选择面板
        "field_catalog": [f.to_dict() for f in ALL_BUILTIN_FIELDS],
        # 每个搜索源支持的最大条数（前端作为 search_result_limit 上限参考）
        "search_result_limit_max": 50,
    }


# ── POST /api/jobs ────────────────────────────────────────────────

@router.post("/jobs")
async def create_job_endpoint(
    file: UploadFile = File(...),
    config: str = Form(default="{}"),
):
    try:
        cfg = JobConfig(**json.loads(config))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"config 解析失败: {exc}")

    # ── 解析 field_defs ──
    if cfg.field_defs:
        field_defs: list[FieldDef] = [fdin.to_field_def() for fdin in cfg.field_defs]
    else:
        field_defs = list(ALL_BUILTIN_FIELDS)

    if not field_defs:
        raise HTTPException(status_code=400, detail="field_defs 不能为空")

    # ── 读取 Excel ──
    try:
        content = await file.read()
        df = pd.read_excel(io.BytesIO(content), header=0)
        col_idx = _pick_company_column(df)
        companies, pre_results = _parse_resume_data(df, col_idx, field_defs)
    except Exception as exc:
        logger.warning("Excel 读取失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=400, detail=f"Excel 读取失败: {exc}")

    if not companies:
        cols = [str(c) for c in df.columns.tolist()] if "df" in locals() else []
        raise HTTPException(
            status_code=400,
            detail=f"Excel 中未找到任何企业名称（确认包含企业名称列）。检测到列名: {cols}",
        )

    pre_done = sum(1 for r in pre_results if r is not None)
    logger.info("任务创建：共 %d 家，续传 %d 家，待处理 %d 家", len(companies), pre_done, len(companies) - pre_done)

    # ── 构建搜索 Provider 列表 ──
    search_providers: list[SearchProvider] = []
    requested = cfg.search_providers or ["metaso"]

    if "metaso" in requested:
        key = cfg.metaso_api_key or settings.metaso_api_key
        if not key:
            raise HTTPException(status_code=400, detail="未配置秘塔 API Key")
        search_providers.append(MetasoProvider(api_key=key))

    if "baidu" in requested:
        key = cfg.baidu_api_key or settings.baidu_api_key
        if not key:
            raise HTTPException(status_code=400, detail="未配置百度千帆 API Key")
        search_providers.append(BaiduQianfanProvider(api_key=key))

    if not search_providers:
        raise HTTPException(status_code=400, detail="至少需要选择一个搜索源")

    # ── 构建 LLM Provider ──
    try:
        llm_cfg = LLMConfig(
            provider=cfg.llm.provider,
            base_url=cfg.llm.base_url or "",
            model=cfg.llm.model or "",
            api_key=cfg.llm.api_key,
        )
        llm_provider = build_llm_provider(llm_cfg)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # ── 创建 Job 并启动后台任务 ──
    job = create_job(companies)
    job.status = JobStatus.RUNNING
    concurrency = ConcurrencyConfig(search=cfg.concurrency.search, llm=cfg.concurrency.llm)

    async def _run():
        try:
            results = await run_pipeline(
                companies=companies,
                search_providers=search_providers,
                llm_provider=llm_provider,
                concurrency=concurrency,
                event_queue=job.event_queue,
                field_defs=field_defs,
                search_result_limit=cfg.search_result_limit,
                pre_results=pre_results,
                cancel_event=job.cancel_event,
            )
            job.results = results
            job.result_bytes = build_result_excel(results, field_defs)
            job.status = JobStatus.CANCELLED if job.cancel_event.is_set() else JobStatus.DONE
        except Exception as exc:
            logger.exception("Pipeline 运行失败: %s", exc)
            job.status = JobStatus.FAILED
            job.error = str(exc)
        finally:
            for p in search_providers:
                await p.close()
            await llm_provider.close()

    asyncio.create_task(_run())
    return {"job_id": job.id, "total": len(companies), "pre_done": pre_done}


# ── POST /api/jobs/{job_id}/cancel ────────────────────────────────

@router.post("/jobs/{job_id}/cancel")
async def cancel_job_endpoint(job_id: str):
    ok = cancel_job(job_id)
    if not ok:
        raise HTTPException(status_code=400, detail="任务不存在或已结束，无法取消")
    return {"ok": True, "message": "已发送停止信号，当前批次完成后将停止"}


# ── GET /api/jobs/{job_id}/events (SSE) ──────────────────────────

@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    async def event_generator():
        while True:
            try:
                event = await asyncio.wait_for(job.event_queue.get(), timeout=25.0)
                payload = {
                    "event":        event.event,
                    "total":        event.total,
                    "completed":    event.completed,
                    "failed":       event.failed,
                    "skipped":      event.skipped,
                    "company_name": event.company_name,
                    "message":      event.message,
                    "elapsed_s":    round(event.elapsed_s, 1),
                    "eta_s":        round(event.eta_s, 0) if event.eta_s else None,
                    "detail":       event.detail,
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                if event.event == "done":
                    break
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"
                if job.status in (JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELLED):
                    break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── GET /api/jobs/{job_id}/download ──────────────────────────────

@router.get("/jobs/{job_id}/download")
async def download_result(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.status not in (JobStatus.DONE, JobStatus.CANCELLED):
        raise HTTPException(status_code=400, detail=f"任务尚未完成（当前状态: {job.status}）")
    if not job.result_bytes:
        raise HTTPException(status_code=500, detail="结果文件生成失败")

    return Response(
        content=job.result_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="result_{job_id[:8]}.xlsx"'},
    )
