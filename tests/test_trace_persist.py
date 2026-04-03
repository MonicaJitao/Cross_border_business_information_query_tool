"""
Trace 持久化模块的单元测试。
"""
import asyncio
import json
import pytest
from pathlib import Path
from datetime import datetime

from backend.app.services.trace.persist import (
    TraceWriter,
    TracePersistConfig,
    create_trace_record,
)


@pytest.fixture
def temp_trace_dir(tmp_path):
    """创建临时 trace 目录"""
    trace_dir = tmp_path / "trace_logs"
    trace_dir.mkdir()
    return trace_dir


@pytest.fixture
def trace_config(temp_trace_dir):
    """创建测试用的配置"""
    return TracePersistConfig(
        enabled=True,
        base_dir=temp_trace_dir,
    )


@pytest.fixture
def sample_evidence():
    """创建测试用的 evidence 数据"""
    return [
        {
            "title": "测试公司新闻报道",
            "url": "https://example.com/news/123",
            "snippet": "这是一个完整的新闻片段，内容比较长，不应该被截断" * 10,
            "provider_name": "metaso",
            "source": "metaso",
            "published_date": "2024-01-15T10:30:00",
        }
    ]


@pytest.fixture
def sample_trace_record(sample_evidence):
    """创建测试用的 trace 记录"""
    return create_trace_record(
        company_name="测试科技有限公司",
        status="done",
        evidence=sample_evidence,
        user_prompt_full="这是一个完整的 prompt，内容非常长" * 20,
        llm_raw_output_full='{"summary": {"has_overseas": "是"}, "tags": {}}',
        final_result={
            "company_name": "测试科技有限公司",
            "summary": {"has_overseas": "是"},
            "tags": {},
            "evidence_count": 1,
            "sources": ["https://example.com/news/123"],
        },
        error=None,
    )


@pytest.mark.asyncio
async def test_trace_writer_basic_write(trace_config, sample_trace_record):
    """测试基本的 trace 写入功能"""
    job_id = "test_job_001"
    writer = TraceWriter(job_id=job_id, config=trace_config)
    
    await writer.start()
    await writer.enqueue(sample_trace_record)
    await writer.close()
    
    # 验证文件已创建
    trace_file = trace_config.base_dir / f"{job_id}.jsonl"
    assert trace_file.exists(), "Trace 文件应该被创建"
    
    # 验证文件内容
    content = trace_file.read_text(encoding="utf-8")
    lines = [line for line in content.strip().split("\n") if line.strip()]
    assert len(lines) == 1, "应该只有一行记录"
    
    # 解析 JSON 并验证字段
    record = json.loads(lines[0])
    assert record["company_name"] == "测试科技有限公司"
    assert record["status"] == "done"
    assert record["job_id"] == job_id
    assert "schema_version" in record
    assert "ts" in record
    
    # 验证完整字段未被截断
    assert len(record["user_prompt_full"]) > 100, "user_prompt_full 应该完整未被截断"
    assert len(record["llm_raw_output_full"]) > 0, "llm_raw_output_full 应该有内容"
    assert len(record["evidence"]) == 1, "evidence 列表应该有一条"
    assert len(record["evidence"][0]["snippet"]) > 200, "snippet 应该完整未被截断"


@pytest.mark.asyncio
async def test_trace_writer_multiple_records(trace_config):
    """测试写入多条记录"""
    job_id = "test_job_002"
    writer = TraceWriter(job_id=job_id, config=trace_config)
    
    await writer.start()
    
    # 写入 3 条记录
    for i in range(3):
        record = create_trace_record(
            company_name=f"公司{i}",
            status="done",
            evidence=[],
            user_prompt_full=f"prompt {i}",
            llm_raw_output_full=f"output {i}",
            final_result={"company_name": f"公司{i}"},
        )
        await writer.enqueue(record)
    
    await writer.close()
    
    # 验证文件内容
    trace_file = trace_config.base_dir / f"{job_id}.jsonl"
    assert trace_file.exists()
    
    content = trace_file.read_text(encoding="utf-8")
    lines = [line for line in content.strip().split("\n") if line.strip()]
    assert len(lines) == 3, "应该有 3 行记录"
    
    # 验证每行都是有效的 JSON
    for i, line in enumerate(lines):
        record = json.loads(line)
        assert record["company_name"] == f"公司{i}"


@pytest.mark.asyncio
async def test_trace_writer_disabled():
    """测试禁用 trace 写入"""
    config = TracePersistConfig(enabled=False)
    job_id = "test_job_disabled"
    writer = TraceWriter(job_id=job_id, config=config)
    
    # 启动和写入不应该报错，但也不会创建文件
    await writer.start()
    await writer.enqueue({"company_name": "test"})
    await writer.close()
    
    # 验证文件未创建
    trace_file = config.base_dir / f"{job_id}.jsonl"
    assert not trace_file.exists()


@pytest.mark.asyncio
async def test_create_trace_record_fields():
    """测试 create_trace_record 生成的字段是否完整"""
    record = create_trace_record(
        company_name="测试公司",
        status="error",
        evidence=[{"title": "test", "url": "https://test.com", "snippet": "test"}],
        user_prompt_full="完整 prompt",
        llm_raw_output_full="完整 output",
        final_result={"test": "value"},
        error="测试错误信息",
    )
    
    # 验证所有必需字段都存在
    required_fields = [
        "company_name", "status", "evidence", 
        "user_prompt_full", "llm_raw_output_full",
        "final_result", "error"
    ]
    
    for field in required_fields:
        assert field in record, f"缺少字段: {field}"
    
    assert record["company_name"] == "测试公司"
    assert record["status"] == "error"
    assert record["error"] == "测试错误信息"
    assert len(record["evidence"]) == 1


@pytest.mark.asyncio
async def test_trace_file_append_mode(trace_config):
    """测试追加模式：多次 start/close 应该追加而不是覆盖"""
    job_id = "test_job_append"
    
    # 第一次写入
    writer1 = TraceWriter(job_id=job_id, config=trace_config)
    await writer1.start()
    await writer1.enqueue(create_trace_record(
        company_name="公司1", status="done", evidence=[],
        user_prompt_full="p1", llm_raw_output_full="o1",
    ))
    await writer1.close()
    
    # 第二次写入（追加）
    writer2 = TraceWriter(job_id=job_id, config=trace_config)
    await writer2.start()
    await writer2.enqueue(create_trace_record(
        company_name="公司2", status="done", evidence=[],
        user_prompt_full="p2", llm_raw_output_full="o2",
    ))
    await writer2.close()
    
    # 验证文件有 2 行
    trace_file = trace_config.base_dir / f"{job_id}.jsonl"
    content = trace_file.read_text(encoding="utf-8")
    lines = [line for line in content.strip().split("\n") if line.strip()]
    assert len(lines) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
