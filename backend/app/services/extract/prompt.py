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
- "无" = 证据中明确提到不存在该情况，或证据中完全没有相关信息、无法判断

【备注要求】
对于每个字段，必须在对应的 notes 字段中提供足以辅助人工复判的依据：
- 如果填"有"：引用具体证据，包括公司名称、注册号、具体时间、金额等可核查信息（如"天眼查显示其在香港注册有全资子公司XX（Hong Kong）Limited，注册号XXXXXXXX"）
- 如果填"无"：先说明未找到直接记录，再列出证据中出现的任何间接线索（如进出口备案号、海关资质、境外商标注册、合作伙伴提及等）；若无任何间接线索，则说明"证据中无任何相关信息"
- 备注应具体（1-3句话），避免仅重复结论，要能帮助人工判断是否需要进一步核查

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

3. 备注写法示例（仅作示范，不要照抄）：
   - 值为"有"的备注："天眼查显示该公司持股51%的子公司'XX（Vietnam）Co., Ltd.'注册于越南胡志明市，注册资本50万美元。"
   - 值为"无"且有间接线索："未找到该公司直接从事进出口业务的记录，但海关总署网站显示其持有进出口经营权备案（备案号：XXXXXXXX），具备从事进出口业务的资质。"
   - 值为"无"且无间接线索："证据中无任何进出口相关信息，包括备案号、资质证书或合作方提及。"

4. 只依据证据中的内容作答,不要捏造信息。

输出格式为 JSON。如果有 summary 字段,则输出 summary 和 summary_notes 两个对象;如果有 tags 字段,则输出 tags 和 tags_notes 两个对象。字段一一对应。
不要输出任何额外内容。"""


def _build_json_schema_block(field_defs: list[FieldDef]) -> str:
    """
    为 LLM prompt 生成 JSON 格式示例块。
    summary 和 tags 各自成一个 JSON 子对象，键名为 field.id。
    同时生成对应的 summary_notes 和 tags_notes 对象。
    """
    summary_lines = []
    summary_note_lines = []
    tags_lines = []
    tags_note_lines = []

    for fd in field_defs:
        line = f'    "{fd.id}": "{fd.instruction}"'
        note_line = f'    "{fd.id}": "简要说明判断依据"'

        if fd.group == "summary":
            summary_lines.append(line)
            summary_note_lines.append(note_line)
        else:
            tags_lines.append(line)
            tags_note_lines.append(note_line)

    parts = []
    if summary_lines:
        parts.append('  "summary": {\n' + ",\n".join(summary_lines) + "\n  }")
        parts.append('  "summary_notes": {\n' + ",\n".join(summary_note_lines) + "\n  }")
    if tags_lines:
        parts.append('  "tags": {\n' + ",\n".join(tags_lines) + "\n  }")
        parts.append('  "tags_notes": {\n' + ",\n".join(tags_note_lines) + "\n  }")

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

    # 生成约束提示
    notes = [
        '- 严格按照【判断标准】只区分"有"和"无"两种情况，不要填"未提及"。',
        '- 识别境外主体时，需同时关注直接注册和股东关系。',
        '- 区域归类时，按照地理和经济常识进行，欧洲国家统一归入欧美。',
        '- 可多选的字段用顿号分隔，如"香港、东南亚"。',
        '- 每个字段必须在 summary_notes 中提供足以辅助人工复判的依据，不要仅重复结论。',
        '- 当值为"无"时，必须在备注中说明是"未找到直接记录"还是"证据无任何相关信息"，并列出任何间接线索。',
    ]

    # 针对 yesno 字段的特殊约束
    yesno_fields = [f.id for f in field_defs if f.field_type == "yesno"]
    if yesno_fields:
        notes.append(f"- {', '.join(yesno_fields)} 只能填\"有\"或\"无\"，不要填\"未提及\"或其他值。")

    notes_text = "\n".join(notes)

    return (
        f"企业名称：{company_name}\n\n"
        f"以下是从网络搜索到的相关证据（共 {len(evidence_snippets)} 条）：\n"
        f"---\n{evidence_text}\n---\n\n"
        f"请根据上述证据，以 JSON 格式输出以下字段：\n\n"
        f"{schema_block}\n\n"
        f"注意：\n{notes_text}"
    )
