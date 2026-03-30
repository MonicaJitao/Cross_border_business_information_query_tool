"""
动态 Prompt 构建。

根据本次任务选定的 field_defs 动态生成 LLM 输出 JSON 的格式约束，
避免在代码里硬编码字段列表，新增/删除字段时只需改 fields.py。
"""
from .fields import FieldDef

SYSTEM_PROMPT = """你是一名专注于跨境贸易的企业信息分析师。
你的任务是根据用户提供的企业网络搜索证据，提取结构化的跨境业务信息。
请只依据证据中的内容作答，无法判断时如实标注"未提及"或留空，不要捏造信息。
输出严格为 JSON 格式，不要输出任何额外内容。"""


def _build_json_schema_block(field_defs: list[FieldDef]) -> str:
    """
    为 LLM prompt 生成 JSON 格式示例块。
    summary 和 tags 各自成一个 JSON 子对象，键名为 field.id。
    """
    summary_lines = []
    tags_lines = []
    for fd in field_defs:
        line = f'    "{fd.id}": "{fd.instruction}"'
        if fd.group == "summary":
            summary_lines.append(line)
        else:
            tags_lines.append(line)

    parts = []
    if summary_lines:
        parts.append('  "summary": {\n' + ",\n".join(summary_lines) + "\n  }")
    if tags_lines:
        parts.append('  "tags": {\n' + ",\n".join(tags_lines) + "\n  }")

    return "{\n" + ",\n".join(parts) + "\n}"


def build_user_prompt(
    company_name: str,
    evidence_snippets: list[str],
    field_defs: list[FieldDef],
) -> str:
    evidence_text = (
        "\n\n".join(f"[{i+1}] {s}" for i, s in enumerate(evidence_snippets))
        if evidence_snippets
        else "（无搜索结果）"
    )
    schema_block = _build_json_schema_block(field_defs)

    # 按 group 生成约束提示
    yesno_summary_ids = [f.id for f in field_defs if f.group == "summary" and f.field_type == "yesno"]
    yesno_tags_ids    = [f.id for f in field_defs if f.group == "tags"    and f.field_type == "yesno"]

    notes = ["- 无相关证据时一律填\"未提及\"，不要捏造信息。"]
    if yesno_summary_ids:
        notes.append(f"- summary 中的 {', '.join(yesno_summary_ids)} 只填\"有\"或\"无\"。")
    if yesno_tags_ids:
        notes.append(f"- tags 中的 {', '.join(yesno_tags_ids)} 严格只填\"是\"、\"否\"或\"未提及\"。")

    notes_text = "\n".join(notes)

    return (
        f"企业名称：{company_name}\n\n"
        f"以下是从网络搜索到的相关证据（共 {len(evidence_snippets)} 条）：\n"
        f"---\n{evidence_text}\n---\n\n"
        f"请根据上述证据，以 JSON 格式输出以下字段：\n\n"
        f"{schema_block}\n\n"
        f"注意：\n{notes_text}"
    )
