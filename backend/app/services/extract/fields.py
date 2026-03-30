"""
字段目录（Field Catalog）。

所有内置抽取字段在此集中定义，包含：
  - id:                 Python 安全键名，也作为 LLM 输出 JSON 的字段名
  - label:              前端显示名称
  - group:              "summary"（总结维度）或 "tags"（标签维度）
  - col_name:           Excel 导出列标题
  - instruction:        写入 prompt 的格式说明
  - field_type:         "yesno" | "text" | "region" | "amount"（前端辅助约束，不影响后端逻辑）
  - enabled_by_default: 是否默认勾选

自定义字段由前端定义，在运行时随 JobConfig 传入，结构相同。
"""
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class FieldDef:
    id: str
    label: str
    group: str           # "summary" | "tags"
    col_name: str
    instruction: str
    field_type: str      # "yesno" | "text" | "region" | "amount"
    enabled_by_default: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


# ── 总结维度（summary）── 9 个内置字段 ─────────────────────────────────
SUMMARY_FIELDS: list[FieldDef] = [
    FieldDef(
        id="has_hk_entity",
        label="是否有香港主体",
        group="summary",
        col_name="是否有香港主体",
        instruction='企业是否在香港注册有子/分公司，只填"有"或"无"',
        field_type="yesno",
    ),
    FieldDef(
        id="has_overseas_entity",
        label="是否有非香港海外主体",
        group="summary",
        col_name="是否有非香港海外主体",
        instruction='企业是否有除香港以外的其他海外主体，只填"有"或"无"',
        field_type="yesno",
    ),
    FieldDef(
        id="overseas_entity_countries",
        label="海外主体所在国家",
        group="summary",
        col_name="海外主体所在国家",
        instruction='若有境外主体，依次列出国家/地区（顿号分隔），无则填"无"，无法判断填"未提及"',
        field_type="region",
    ),
    FieldDef(
        id="has_import_export",
        label="是否有进出口业务",
        group="summary",
        col_name="是否有进出口业务",
        instruction='企业是否有进出口业务，只填"有"或"无"',
        field_type="yesno",
    ),
    FieldDef(
        id="import_export_countries",
        label="进出口业务涉及国家",
        group="summary",
        col_name="进出口业务涉及国家",
        instruction='进出口业务涉及的国家/地区（顿号分隔），无法判断则填"未提及"',
        field_type="region",
    ),
    FieldDef(
        id="import_export_mode",
        label="进出口主要模式",
        group="summary",
        col_name="进出口主要模式",
        instruction='只填"主要进口"、"主要出口"或"进出口都有"，无信息填"未提及"',
        field_type="text",
    ),
    FieldDef(
        id="annual_import_export_amount",
        label="年进出口金额",
        group="summary",
        col_name="年进出口金额",
        instruction='上一年全年进出口总额，格式为金额区间+币种，如"3-4亿元人民币"，无信息填"未提及"',
        field_type="amount",
    ),
    FieldDef(
        id="industry",
        label="企业所属行业",
        group="summary",
        col_name="企业所属行业",
        instruction='企业所属的具体行业，如"精密仪器制造"、"跨境电商"等',
        field_type="text",
    ),
    FieldDef(
        id="annual_revenue",
        label="企业年营收规模",
        group="summary",
        col_name="企业年营收规模",
        instruction='上一年全年营收，格式为金额区间+币种，如"2000-3500万元人民币"，无信息填"未提及"',
        field_type="amount",
    ),
]


# ── 标签维度（tags）── 9 个内置字段 ────────────────────────────────────
TAGS_FIELDS: list[FieldDef] = [
    FieldDef(
        id="tag1_import_export",
        label="标签1_进出口业务",
        group="tags",
        col_name="标签1_进出口业务",
        instruction='企业是否有进出口业务，严格只填"是"、"否"或"未提及"',
        field_type="yesno",
    ),
    FieldDef(
        id="tag2_overseas_entity",
        label="标签2_境外主体",
        group="tags",
        col_name="标签2_境外主体",
        instruction='企业是否有境外（含香港）主体，严格只填"是"、"否"或"未提及"',
        field_type="yesno",
    ),
    FieldDef(
        id="tag3_going_overseas",
        label="标签3_出海规划",
        group="tags",
        col_name="标签3_出海规划",
        instruction='企业是否在规划/布局出海业务，严格只填"是"、"否"或"未提及"',
        field_type="yesno",
    ),
    FieldDef(
        id="tag4_forex",
        label="标签4_外汇业务",
        group="tags",
        col_name="标签4_外汇业务",
        instruction='企业是否有外汇业务，严格只填"是"、"否"或"未提及"',
        field_type="yesno",
    ),
    FieldDef(
        id="tag5_fx_settlement",
        label="标签5_结售汇业务",
        group="tags",
        col_name="标签5_结售汇业务",
        instruction='企业是否有结售汇业务，严格只填"是"、"否"或"未提及"',
        field_type="yesno",
    ),
    FieldDef(
        id="tag6_industry",
        label="标签6_客户行业",
        group="tags",
        col_name="标签6_客户行业",
        instruction='客户所属行业，根据实际情况提取，无信息填"未提及"',
        field_type="text",
    ),
    FieldDef(
        id="tag7_business_scale",
        label="标签7_经营规模",
        group="tags",
        col_name="标签7_经营规模",
        instruction='客户境内外经营规模描述，根据实际情况提取，无信息填"未提及"',
        field_type="text",
    ),
    FieldDef(
        id="tag8_import_export_region",
        label="标签8_进出口地区",
        group="tags",
        col_name="标签8_进出口地区",
        instruction='客户进出口业务主要地区，根据实际情况提取，无信息填"未提及"',
        field_type="region",
    ),
    FieldDef(
        id="tag9_overseas_region",
        label="标签9_出海地区",
        group="tags",
        col_name="标签9_出海地区",
        instruction='客户出海业务主要地区，根据实际情况提取，无信息填"未提及"',
        field_type="region",
    ),
]


# 全量内置字段列表（前端 /api/meta 返回此列表）
ALL_BUILTIN_FIELDS: list[FieldDef] = SUMMARY_FIELDS + TAGS_FIELDS

# col_name → FieldDef 的快速查找（用于续传时匹配历史 Excel 列）
_COL_NAME_INDEX: dict[str, FieldDef] = {f.col_name: f for f in ALL_BUILTIN_FIELDS}


def find_by_col_name(col_name: str) -> Optional[FieldDef]:
    return _COL_NAME_INDEX.get(col_name)
