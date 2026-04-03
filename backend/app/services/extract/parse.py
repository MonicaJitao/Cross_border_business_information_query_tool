"""
三层 JSON 解析 fallback + 引号修复，应对 LLM 返回格式不规范的情况。
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


def _try_repair_quotes(text: str) -> Optional[dict]:
    """
    用状态机修复 LLM 输出中未转义的双引号。

    LLM 在 JSON 字符串值里经常输出未转义的 " （如 "技术进出口"），
    导致标准 json.loads 失败。此函数通过上下文判断哪些 " 是字符串
    边界、哪些是内容中的引号，对后者自动加 \\ 转义。
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    raw = text[start:end + 1]
    result = []
    i = 0
    in_string = False

    while i < len(raw):
        ch = raw[i]

        if not in_string:
            result.append(ch)
            if ch == '"':
                in_string = True
        else:
            if ch == '\\' and i + 1 < len(raw):
                result.append(ch)
                i += 1
                result.append(raw[i])
            elif ch == '"':
                rest = raw[i + 1:].lstrip()
                if not rest or rest[0] in (':', ',', '}', ']', '"'):
                    result.append(ch)
                    in_string = False
                else:
                    result.append('\\"')
            elif ch == '\n':
                result.append('\\n')
            else:
                result.append(ch)

        i += 1

    repaired = ''.join(result)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        logger.debug("引号修复后仍无法解析，前 300 字: %s", repaired[:300])
        return None


def parse_llm_json(text: str) -> tuple[Optional[dict], str]:
    """
    Returns: (parsed_dict, strategy_used)
    strategy_used: "direct" | "code_block" | "brace_extract" | "repair_quotes" | "failed"
    """
    result = _try_direct(text)
    if result is not None:
        strategy = "direct"
    else:
        result = _try_extract_block(text)
        if result is not None:
            strategy = "code_block"
        else:
            result = _try_extract_brace(text)
            if result is not None:
                strategy = "brace_extract"
            else:
                result = _try_repair_quotes(text)
                if result is not None:
                    strategy = "repair_quotes"
                else:
                    logger.warning("JSON 解析全部失败，原文前 200 字: %s", text[:200])
                    return None, "failed"

    # 如果解析成功，确保包含 summary_notes 和 tags_notes
    if result is not None:
        if "summary" in result and "summary_notes" not in result:
            result["summary_notes"] = {}
        if "tags" in result and "tags_notes" not in result:
            result["tags_notes"] = {}

    return result, strategy
