"""
Trace 落盘持久化模块。

使用 asyncio.Queue + 单独 writer task 实现并发安全的 JSONL 写入。
每个 job 生成一个 {job_id}.jsonl 文件，每家公司一行记录。
"""
import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TracePersistConfig:
    """Trace 持久化配置"""
    enabled: bool = True
    base_dir: Path = Path("backend/app/logs/jobs")
    encoding: str = "utf-8"
    queue_maxsize: int = 1000  # 防止内存爆炸


class TraceWriter:
    """
    异步 JSONL 写入器。

    使用 Queue + 后台 writer task 实现并发安全：
    - 多个 process_one() 协程可以并发 enqueue
    - 单个 writer task 串行写入文件，避免文件锁冲突
    """

    def __init__(self, job_id: str, config: TracePersistConfig):
        self.job_id = job_id
        self.config = config
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=config.queue_maxsize)
        self.writer_task: Optional[asyncio.Task] = None
        self.file_path: Optional[Path] = None
        self._closed = False

    async def start(self) -> None:
        """启动 writer task"""
        if not self.config.enabled:
            logger.info("Trace persist disabled, skipping writer start")
            return

        # 确保目录存在
        self.config.base_dir.mkdir(parents=True, exist_ok=True)
        self.file_path = self.config.base_dir / f"{self.job_id}.jsonl"

        # 启动后台写入任务
        self.writer_task = asyncio.create_task(self._writer_loop())
        logger.info("TraceWriter started for job %s -> %s", self.job_id, self.file_path)

    async def enqueue(self, record: dict[str, Any]) -> None:
        """
        将一条记录加入写入队列。

        Args:
            record: 包含 company_name, status, evidence, user_prompt_full 等字段的字典
        """
        if not self.config.enabled or self._closed:
            return

        # 添加 schema_version 和时间戳
        record.setdefault("schema_version", 1)
        record.setdefault("ts", datetime.utcnow().isoformat() + "Z")
        record.setdefault("job_id", self.job_id)

        try:
            await asyncio.wait_for(self.queue.put(record), timeout=5.0)
        except asyncio.TimeoutError:
            logger.error("TraceWriter queue full, dropping record for %s", record.get("company_name"))
        except Exception as e:
            logger.exception("Failed to enqueue trace record: %s", e)

    async def close(self) -> None:
        """关闭 writer，等待队列清空"""
        if self._closed or not self.config.enabled:
            return

        self._closed = True

        # 发送哨兵值通知 writer 退出
        await self.queue.put(None)

        # 等待 writer task 完成
        if self.writer_task:
            try:
                await asyncio.wait_for(self.writer_task, timeout=30.0)
                logger.info("TraceWriter closed for job %s", self.job_id)
            except asyncio.TimeoutError:
                logger.warning("TraceWriter close timeout for job %s", self.job_id)
                self.writer_task.cancel()
            except Exception as e:
                logger.exception("Error closing TraceWriter: %s", e)

    async def _writer_loop(self) -> None:
        """后台写入循环，串行处理队列中的记录"""
        if not self.file_path:
            logger.error("file_path not set, writer loop exiting")
            return

        try:
            # 使用 asyncio.to_thread 避免阻塞事件循环
            with open(self.file_path, "a", encoding=self.config.encoding) as f:
                while True:
                    record = await self.queue.get()

                    # 哨兵值，退出循环
                    if record is None:
                        break

                    try:
                        # 写入 JSONL（每行一个 JSON 对象）
                        line = json.dumps(record, ensure_ascii=False) + "\n"
                        await asyncio.to_thread(f.write, line)
                        await asyncio.to_thread(f.flush)
                    except Exception as e:
                        logger.exception("Failed to write trace record: %s", e)
                    finally:
                        self.queue.task_done()

        except Exception as e:
            logger.exception("Writer loop crashed: %s", e)


def create_trace_record(
    company_name: str,
    status: str,
    evidence: list[dict],
    user_prompt_full: str,
    llm_raw_output_full: str,
    final_result: Optional[dict] = None,
    error: Optional[str] = None,
) -> dict[str, Any]:
    """
    构造一条完整的 trace 记录。

    Args:
        company_name: 公司名称
        status: done | error | cancelled
        evidence: 完整的 SearchResult 列表（转为 dict）
        user_prompt_full: 完整的 user prompt（不截断）
        llm_raw_output_full: 完整的 LLM 原始输出（不截断）
        final_result: 最终提取结果（CompanyExtraction.model_dump(exclude={"trace"})）
        error: 错误信息（如有）

    Returns:
        可直接写入 JSONL 的 dict
    """
    return {
        "company_name": company_name,
        "status": status,
        "evidence": evidence,
        "user_prompt_full": user_prompt_full,
        "llm_raw_output_full": llm_raw_output_full,
        "final_result": final_result or {},
        "error": error,
    }
