"""
三层 JSON 解析 fallback，应对 LLM 返回格式不规范的情况。
"""
import json
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _try_direct(text: str) -> Optional[dict]:
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None


def _try_extract_block(text: str) -> Optional[dict]:
    """从 markdown 代码块中提取 JSON"""
    pattern = r"```(?:json)?\s*([\s\S]+?)\s*```"
    match = re.search(pattern, text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None


def _try_extract_brace(text: str) -> Optional[dict]:
    """找到第一个 { 和最后一个 } 的内容"""
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None


def parse_llm_json(text: str) -> tuple[Optional[dict], str]:
    """
    Returns: (parsed_dict, strategy_used)
    strategy_used: "direct" | "code_block" | "brace_extract" | "failed"
    """
    result = _try_direct(text)
    if result is not None:
        return result, "direct"

    result = _try_extract_block(text)
    if result is not None:
        return result, "code_block"

    result = _try_extract_brace(text)
    if result is not None:
        return result, "brace_extract"

    logger.warning("JSON 解析全部失败，原文前 200 字: %s", text[:200])
    return None, "failed"
