"""
内存级 Job 存储（MVP）。
重启后任务丢失 — 与原始设计一致，后续可替换为 SQLite。

build_result_excel 接受动态 field_defs，只导出本次任务选定的字段列。
"""
import asyncio
import io
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import pandas as pd

from ..extract.schema import CompanyExtraction
from ..extract.fields import FieldDef


class JobStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    DONE      = "done"
    CANCELLED = "cancelled"
    FAILED    = "failed"


@dataclass
class Job:
    id: str
    status: JobStatus = JobStatus.PENDING
    companies: list[str] = field(default_factory=list)
    results: list[CompanyExtraction] = field(default_factory=list)
    event_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    error: Optional[str] = None
    result_bytes: Optional[bytes] = None


_store: dict[str, Job] = {}


def create_job(companies: list[str]) -> Job:
    job_id = str(uuid.uuid4())
    job = Job(id=job_id, companies=companies)
    _store[job_id] = job
    return job


def get_job(job_id: str) -> Optional[Job]:
    return _store.get(job_id)


def cancel_job(job_id: str) -> bool:
    job = _store.get(job_id)
    if not job or job.status not in (JobStatus.RUNNING, JobStatus.PENDING):
        return False
    job.cancel_event.set()
    return True


def build_result_excel(results: list[CompanyExtraction], field_defs: list[FieldDef]) -> bytes:
    """
    按照本次任务的 field_defs 动态构建 Excel。
    公共列（企业名称/证据条数/来源URL/错误信息）始终包含。
    """
    rows = []
    for r in results:
        row: dict = {"企业名称": r.company_name}

        for fd in field_defs:
            if fd.group == "summary":
                row[fd.col_name] = r.summary.get(fd.id, "")
            else:
                row[fd.col_name] = r.tags.get(fd.id, "")

        row["证据条数"] = r.evidence_count
        row["来源URL"]  = " | ".join(r.sources)
        row["错误信息"] = r.error or ""
        rows.append(row)

    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="跨境信息")
    return buf.getvalue()
