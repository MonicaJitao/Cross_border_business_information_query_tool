"""
动态 Prompt 构建。

根据本次任务选定的 field_defs 动态生成 LLM 输出 JSON 的格式约束，
避免在代码里硬编码字段列表，新增/删除字段时只需改 fields.py。
"""
from .fields import FieldDef

SYSTEM_PROMPT = """你是一名专注于跨境贸易的企业信息分析师。
你的任务是根据用户提供的企业网络搜索证据,提取结构化的跨境业务信息。

【判断标准】
- "有" = 证据中明确提到存在该情况
- "无" = 证据中明确提到不存在该情况
- "未提及" = 证据中完全没有相关信息,无法判断

【备注要求】
对于每个字段,必须在对应的 notes 字段中简要说明判断依据:
- 如果填"有"或"无":引用证据中的关键信息(如"网页明确提到...")
- 如果填"未提及":说明"证据中无相关信息"
- 备注应简洁(1-2句话),直接引用关键证据

【特殊说明】
1. 境外主体识别:
   - 包括企业直接注册的境外子公司、分公司
   - 也包括通过股东关系(控股、参股)关联的境外主体
   - 需关注"股东"、"控股"、"投资"、"子公司"等关键词

2. 区域归类规则:
   - 香港 → 香港
   - 东南亚国家(泰国/越南/新加坡/马来西亚/印尼/菲律宾等)→ 东南亚
   - 欧美国家(美国/英国/德国/法国/西班牙/意大利/荷兰/加拿大/澳大利亚等)→ 欧美
   - 中东国家(迪拜/沙特/阿联酋/卡塔尔等)→ 中东
   - 非洲/拉美/其他未列明地区 → 其他
   - 可多选,用顿号分隔(如"香港、东南亚、欧美、中东、其他")

3. 只依据证据中的内容作答,不要捏造信息。

输出格式为 JSON,包含 summary、summary_notes 两个对象,字段一一对应。
不要输出任何额外内容。"""


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
