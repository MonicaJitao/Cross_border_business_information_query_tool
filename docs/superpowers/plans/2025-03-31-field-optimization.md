# 字段优化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 简化字段结构从 18 个到 10 个，添加备注字段系统，优化搜索关键词和提示词

**Architecture:** 采用渐进式迁移策略，先修改数据模型和字段定义，再优化提示词和搜索逻辑，最后适配前端展示。保持向后兼容性，确保旧版本 Excel 可以正常续传。

**Tech Stack:** Python 3.9+, FastAPI, Pydantic, Pandas, JavaScript (Vanilla)

---

## 文件结构概览

**后端修改：**
- `backend/app/services/extract/schema.py` - 添加 summary_notes 和 tags_notes 字段
- `backend/app/services/extract/fields.py` - 重构字段定义（10 个字段）
- `backend/app/services/extract/prompt.py` - 优化 SYSTEM_PROMPT 和 JSON Schema 生成
- `backend/app/services/extract/parse.py` - 适配 summary_notes 解析
- `backend/app/services/pipeline/keywords.py` - 优化搜索关键词（2 组）
- `backend/app/services/storage/job_store.py` - 调整 Excel 导出逻辑

**前端修改：**
- `frontend/app.js` - 字段面板渲染、企业详情展示
- `frontend/styles.css` - 备注字段样式

**测试文件：**
- `tests/test_fields.py` - 字段定义测试
- `tests/test_prompt.py` - 提示词生成测试
- `tests/test_parse.py` - JSON 解析测试
- `tests/test_excel.py` - Excel 导出测试

---

## Task 1: 数据模型添加备注字段

**Files:**
- Modify: `backend/app/services/extract/schema.py:26-36`

- [ ] **Step 1: 添加备注字段到 CompanyExtraction 模型**

在 `CompanyExtraction` 类中添加 `summary_notes` 和 `tags_notes` 字段：

```python
class CompanyExtraction(BaseModel):
    company_name: str
    summary: dict[str, str] = Field(default_factory=dict)
    summary_notes: dict[str, str] = Field(default_factory=dict)  # 新增
    tags: dict[str, str] = Field(default_factory=dict)
    tags_notes: dict[str, str] = Field(default_factory=dict)      # 新增
    evidence_count: int = 0
    sources: list[str] = Field(default_factory=list)
    error: Optional[str] = None
    trace: CompanyTrace = Field(default_factory=CompanyTrace)
```

- [ ] **Step 2: 验证模型可以正常实例化**

创建测试文件验证：

```python
# tests/test_schema.py
from backend.app.services.extract.schema import CompanyExtraction

def test_company_extraction_with_notes():
    extraction = CompanyExtraction(
        company_name="测试公司",
        summary={"has_hk_entity": "有"},
        summary_notes={"has_hk_entity": "网页明确提到在香港有子公司"},
    )
    assert extraction.summary_notes["has_hk_entity"] == "网页明确提到在香港有子公司"
    assert extraction.tags_notes == {}
```

- [ ] **Step 3: 运行测试验证**

Run: `pytest tests/test_schema.py::test_company_extraction_with_notes -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/extract/schema.py tests/test_schema.py
git commit -m "feat(schema): add summary_notes and tags_notes fields to CompanyExtraction"
```

---

## Task 2: 重构字段定义（删除标签维度，保留 10 个字段）

**Files:**
- Modify: `backend/app/services/extract/fields.py:33-196`

- [ ] **Step 1: 写测试验证新字段结构**

```python
# tests/test_fields.py
from backend.app.services.extract.fields import ALL_BUILTIN_FIELDS, SUMMARY_FIELDS, TAGS_FIELDS

def test_field_count():
    """验证字段总数为 10 个，全部在 summary 组"""
    assert len(ALL_BUILTIN_FIELDS) == 10
    assert len(SUMMARY_FIELDS) == 10
    assert len(TAGS_FIELDS) == 0

def test_has_going_overseas_field():
    """验证出海规划字段已移至 summary 组"""
    field_ids = [f.id for f in SUMMARY_FIELDS]
    assert "has_going_overseas" in field_ids

def test_region_fields():
    """验证区域字段的 instruction 包含枚举值"""
    region_fields = [f for f in SUMMARY_FIELDS if "region" in f.id]
    assert len(region_fields) == 2
    for f in region_fields:
        assert "香港、东南亚、欧美、中东、其他" in f.instruction
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_fields.py -v`
Expected: FAIL (字段数量不匹配)

- [ ] **Step 3: 重构 SUMMARY_FIELDS（10 个字段）**

```python
# backend/app/services/extract/fields.py
SUMMARY_FIELDS: list[FieldDef] = [
    FieldDef(
        id="has_hk_entity",
        label="是否有香港主体",
        group="summary",
        col_name="是否有香港主体",
        instruction='证据中是否明确提到企业在香港有注册主体（子公司/分公司），或通过股东关系关联香港主体。明确有填"有"，明确无填"无"，无相关信息填"未提及"',
        field_type="yesno",
    ),
    FieldDef(
        id="has_overseas_entity",
        label="是否有非香港海外主体",
        group="summary",
        col_name="是否有非香港海外主体",
        instruction='证据中是否明确提到企业在香港以外有海外主体，或通过股东关系关联海外主体。明确有填"有"，明确无填"无"，无相关信息填"未提及"',
        field_type="yesno",
    ),
    FieldDef(
        id="overseas_entity_regions",
        label="海外主体所在区域",
        group="summary",
        col_name="海外主体所在区域",
        instruction='若有境外主体，按地理区域归类，可多选（顿号分隔）。枚举值：香港、东南亚、欧美、中东、其他。归类示例：泰国/越南→东南亚，美国/英国/西班牙→欧美，迪拜/沙特→中东。无境外主体填"无"，无法判断填"未提及"',
        field_type="region",
    ),
    FieldDef(
        id="has_import_export",
        label="是否有进出口业务",
        group="summary",
        col_name="是否有进出口业务",
        instruction='证据中是否明确提到企业有进出口业务。明确有填"有"，明确无填"无"，无相关信息填"未提及"',
        field_type="yesno",
    ),
    FieldDef(
        id="import_export_regions",
        label="进出口业务涉及区域",
        group="summary",
        col_name="进出口业务涉及区域",
        instruction='进出口业务涉及的地理区域，可多选（顿号分隔）。枚举值：香港、东南亚、欧美、中东、其他。归类规则同"海外主体所在区域"。无进出口业务填"无"，无法判断填"未提及"',
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
    FieldDef(
        id="has_going_overseas",
        label="是否有出海规划",
        group="summary",
        col_name="是否有出海规划",
        instruction='证据中是否明确提到企业在规划、布局或拓展海外市场/国际化业务。明确有填"有"，明确无填"无"，无相关信息填"未提及"',
        field_type="yesno",
    ),
]
```

- [ ] **Step 4: 清空 TAGS_FIELDS**

```python
# backend/app/services/extract/fields.py
TAGS_FIELDS: list[FieldDef] = []
```

- [ ] **Step 5: 运行测试验证通过**

Run: `pytest tests/test_fields.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/extract/fields.py tests/test_fields.py
git commit -m "feat(fields): restructure to 10 summary fields, remove tags fields

- Move has_going_overseas from tags to summary
- Change country fields to region fields with enum values
- Add shareholder relationship to instructions
- Clear TAGS_FIELDS"
```

---

## Task 3: 优化 SYSTEM_PROMPT

**Files:**
- Modify: `backend/app/services/extract/prompt.py:9-12`

- [ ] **Step 1: 写测试验证新 SYSTEM_PROMPT 包含关键内容**

```python
# tests/test_prompt.py
from backend.app.services.extract.prompt import SYSTEM_PROMPT

def test_system_prompt_has_judgment_criteria():
    """验证 SYSTEM_PROMPT 包含判断标准"""
    assert "【判断标准】" in SYSTEM_PROMPT
    assert '"有" = 证据中明确提到存在该情况' in SYSTEM_PROMPT
    assert '"无" = 证据中明确提到不存在该情况' in SYSTEM_PROMPT
    assert '"未提及" = 证据中完全没有相关信息' in SYSTEM_PROMPT

def test_system_prompt_has_notes_requirement():
    """验证 SYSTEM_PROMPT 包含备注要求"""
    assert "【备注要求】" in SYSTEM_PROMPT
    assert "summary_notes" in SYSTEM_PROMPT

def test_system_prompt_has_shareholder_guidance():
    """验证 SYSTEM_PROMPT 包含股东关系识别指引"""
    assert "股东关系" in SYSTEM_PROMPT
    assert "控股" in SYSTEM_PROMPT

def test_system_prompt_has_region_rules():
    """验证 SYSTEM_PROMPT 包含区域归类规则"""
    assert "区域归类规则" in SYSTEM_PROMPT
    assert "香港、东南亚、欧美、中东、其他" in SYSTEM_PROMPT
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_prompt.py::test_system_prompt_has_judgment_criteria -v`
Expected: FAIL

- [ ] **Step 3: 更新 SYSTEM_PROMPT**

```python
# backend/app/services/extract/prompt.py
SYSTEM_PROMPT = """你是一名专注于跨境贸易的企业信息分析师。
你的任务是根据用户提供的企业网络搜索证据，提取结构化的跨境业务信息。

【判断标准】
- "有" = 证据中明确提到存在该情况
- "无" = 证据中明确提到不存在该情况
- "未提及" = 证据中完全没有相关信息，无法判断

【备注要求】
对于每个字段，必须在对应的 notes 字段中简要说明判断依据：
- 如果填"有"或"无"：引用证据中的关键信息（如"网页明确提到..."）
- 如果填"未提及"：说明"证据中无相关信息"
- 备注应简洁（1-2句话），直接引用关键证据

【特殊说明】
1. 境外主体识别：
   - 包括企业直接注册的境外子公司、分公司
   - 也包括通过股东关系（控股、参股）关联的境外主体
   - 需关注"股东"、"控股"、"投资"、"子公司"等关键词

2. 区域归类规则：
   - 香港 → 香港
   - 东南亚国家（泰国/越南/新加坡/马来西亚/印尼/菲律宾等）→ 东南亚
   - 欧美国家（美国/英国/德国/法国/西班牙/意大利/荷兰/加拿大/澳大利亚等）→ 欧美
   - 中东国家（迪拜/沙特/阿联酋/卡塔尔等）→ 中东
   - 非洲/拉美/其他未列明地区 → 其他
   - 可多选，用顿号分隔（如"香港、东南亚、欧美"）

3. 只依据证据中的内容作答，不要捏造信息。

输出格式为 JSON，包含 summary、summary_notes 两个对象，字段一一对应。
不要输出任何额外内容。"""
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_prompt.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/extract/prompt.py tests/test_prompt.py
git commit -m "feat(prompt): enhance SYSTEM_PROMPT with judgment criteria and notes requirement

- Add clear definition for yes/no/not-mentioned
- Add notes requirement for explainability
- Add shareholder relationship identification guidance
- Add region classification rules"
```

---

## Task 4: 更新 JSON Schema 生成逻辑（包含 summary_notes）

**Files:**
- Modify: `backend/app/services/extract/prompt.py:15-35`

- [ ] **Step 1: 写测试验证 JSON Schema 包含 summary_notes**

```python
# tests/test_prompt.py (追加)
from backend.app.services.extract.prompt import _build_json_schema_block
from backend.app.services.extract.fields import FieldDef

def test_json_schema_includes_summary_notes():
    """验证 JSON Schema 包含 summary_notes 对象"""
    field_defs = [
        FieldDef(
            id="has_hk_entity",
            label="是否有香港主体",
            group="summary",
            col_name="是否有香港主体",
            instruction="测试指令",
            field_type="yesno",
        ),
    ]
    schema = _build_json_schema_block(field_defs)
    assert '"summary"' in schema
    assert '"summary_notes"' in schema
    assert '"has_hk_entity"' in schema
    assert "简要说明判断依据" in schema
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_prompt.py::test_json_schema_includes_summary_notes -v`
Expected: FAIL

- [ ] **Step 3: 修改 _build_json_schema_block 函数**

```python
# backend/app/services/extract/prompt.py
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
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_prompt.py::test_json_schema_includes_summary_notes -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/extract/prompt.py tests/test_prompt.py
git commit -m "feat(prompt): add summary_notes to JSON schema generation"
```

---

## Task 5: 更新动态约束提示（包含备注要求）

**Files:**
- Modify: `backend/app/services/extract/prompt.py:38-69`

- [ ] **Step 1: 写测试验证约束提示包含备注要求**

```python
# tests/test_prompt.py (追加)
from backend.app.services.extract.prompt import build_user_prompt

def test_user_prompt_includes_notes_requirement():
    """验证 user prompt 包含备注要求"""
    field_defs = [
        FieldDef(
            id="has_hk_entity",
            label="是否有香港主体",
            group="summary",
            col_name="是否有香港主体",
            instruction="测试指令",
            field_type="yesno",
        ),
    ]
    prompt = build_user_prompt("测试公司", ["证据1"], field_defs)
    assert "每个字段必须在 summary_notes 中提供判断依据" in prompt
    assert "识别境外主体时，需同时关注直接注册和股东关系" in prompt
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_prompt.py::test_user_prompt_includes_notes_requirement -v`
Expected: FAIL

- [ ] **Step 3: 修改 build_user_prompt 函数的 notes 部分**

```python
# backend/app/services/extract/prompt.py (修改 build_user_prompt 函数)
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
        "- 严格按照【判断标准】区分"有"、"无"、"未提及"三种情况。",
        "- 识别境外主体时，需同时关注直接注册和股东关系。",
        "- 区域归类时，按照地理和经济常识进行，欧洲国家统一归入欧美。",
        "- 可多选的字段用顿号分隔，如"香港、东南亚"。",
        "- 每个字段必须在 summary_notes 中提供判断依据。",
    ]

    # 针对 yesno 字段的特殊约束
    yesno_fields = [f.id for f in field_defs if f.field_type == "yesno"]
    if yesno_fields:
        notes.append(f"- {', '.join(yesno_fields)} 只能填\"有\"、\"无\"或\"未提及\"，不要填其他值。")

    notes_text = "\n".join(notes)

    return (
        f"企业名称：{company_name}\n\n"
        f"以下是从网络搜索到的相关证据（共 {len(evidence_snippets)} 条）：\n"
        f"---\n{evidence_text}\n---\n\n"
        f"请根据上述证据，以 JSON 格式输出以下字段：\n\n"
        f"{schema_block}\n\n"
        f"注意：\n{notes_text}"
    )
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_prompt.py::test_user_prompt_includes_notes_requirement -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/extract/prompt.py tests/test_prompt.py
git commit -m "feat(prompt): enhance user prompt with notes requirement and constraints"
```

---

## Task 6: 适配 JSON 解析逻辑（处理 summary_notes）

**Files:**
- Modify: `backend/app/services/extract/parse.py`

- [ ] **Step 1: 写测试验证 parse_llm_json 可以解析包含 summary_notes 的 JSON**

```python
# tests/test_parse.py
from backend.app.services.extract.parse import parse_llm_json
import json

def test_parse_json_with_summary_notes():
    """验证可以解析包含 summary_notes 的 JSON"""
    llm_output = json.dumps({
        "summary": {"has_hk_entity": "有"},
        "summary_notes": {"has_hk_entity": "网页明确提到在香港有子公司"}
    }, ensure_ascii=False)
    
    parsed, strategy = parse_llm_json(llm_output)
    assert parsed is not None
    assert parsed["summary"]["has_hk_entity"] == "有"
    assert parsed["summary_notes"]["has_hk_entity"] == "网页明确提到在香港有子公司"

def test_parse_json_without_summary_notes():
    """验证兼容不包含 summary_notes 的旧格式 JSON"""
    llm_output = json.dumps({
        "summary": {"has_hk_entity": "有"}
    }, ensure_ascii=False)
    
    parsed, strategy = parse_llm_json(llm_output)
    assert parsed is not None
    assert parsed["summary"]["has_hk_entity"] == "有"
    # 应该自动补充空的 summary_notes
    assert "summary_notes" in parsed
    assert isinstance(parsed["summary_notes"], dict)
```

- [ ] **Step 2: 运行测试验证当前行为**

Run: `pytest tests/test_parse.py -v`
Expected: 第二个测试可能 FAIL（如果没有自动补充 summary_notes）

- [ ] **Step 3: 修改 parse_llm_json 函数添加兼容逻辑**

在 `parse.py` 的 `parse_llm_json` 函数末尾添加兼容逻辑：

```python
# backend/app/services/extract/parse.py (在函数末尾添加)
def parse_llm_json(raw_output: str) -> tuple[Optional[dict], str]:
    # ... 现有的解析逻辑 ...
    
    # 如果解析成功，确保包含 summary_notes 和 tags_notes
    if parsed is not None:
        if "summary" in parsed and "summary_notes" not in parsed:
            parsed["summary_notes"] = {}
        if "tags" in parsed and "tags_notes" not in parsed:
            parsed["tags_notes"] = {}
    
    return parsed, strategy
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_parse.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/extract/parse.py tests/test_parse.py
git commit -m "feat(parse): add backward compatibility for summary_notes parsing"
```

---

## Task 7: 优化搜索关键词（从 3 组到 2 组）

**Files:**
- Modify: `backend/app/services/pipeline/keywords.py:10-16`

- [ ] **Step 1: 写测试验证新关键词组**

```python
# tests/test_keywords.py
from backend.app.services.pipeline.keywords import build_keyword_groups

def test_keyword_groups_count():
    """验证关键词组数量为 2"""
    groups = build_keyword_groups("测试公司")
    assert len(groups) == 2

def test_first_group_contains_core_keywords():
    """验证第 1 组包含核心关键词"""
    groups = build_keyword_groups("测试公司")
    first_group = groups[0]
    assert "测试公司" in first_group
    assert "股东" in first_group
    assert "香港" in first_group
    assert "海外" in first_group
    assert "进出口" in first_group
    assert "跨境" in first_group

def test_second_group_contains_supplementary_keywords():
    """验证第 2 组包含补充关键词"""
    groups = build_keyword_groups("测试公司")
    second_group = groups[1]
    assert "测试公司" in second_group
    assert "出海" in second_group
    assert "国际化" in second_group
    assert "营收" in second_group
    assert "年报" in second_group
    assert "行业" in second_group
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_keywords.py -v`
Expected: FAIL (关键词组数量不匹配)

- [ ] **Step 3: 修改 build_keyword_groups 函数**

```python
# backend/app/services/pipeline/keywords.py
"""
为每家企业生成 2 组搜索关键词。
第 1 组信息密度最高（境外主体 + 进出口），第 2 组补充细节（出海规划 + 营收行业）。
"""

MIN_RESULTS_TO_SKIP = 5  # 保留此常量，虽然现在不跳过


def build_keyword_groups(company_name: str) -> list[str]:
    """返回有序的 2 组查询字符串。优先度从高到低。"""
    return [
        # 第 1 组：境外主体 + 进出口（核心业务）
        # 覆盖字段：has_hk_entity, has_overseas_entity, overseas_entity_regions,
        #          has_import_export, import_export_regions, import_export_mode
        f"{company_name} 股东 香港 海外 进出口 跨境",

        # 第 2 组：出海规划 + 营收行业（补充信息）
        # 覆盖字段：has_going_overseas, industry, annual_revenue,
        #          annual_import_export_amount
        f"{company_name} 出海 国际化 营收 年报 行业",
    ]
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_keywords.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/pipeline/keywords.py tests/test_keywords.py
git commit -m "feat(keywords): optimize search keywords from 3 groups to 2 groups

- Group 1: shareholder + HK + overseas + import/export
- Group 2: going overseas + revenue + industry"
```

---

## Task 8: 调整 Excel 导出逻辑（字段 + 备注交替）

**Files:**
- Modify: `backend/app/services/storage/job_store.py:62-86`

- [ ] **Step 1: 写测试验证 Excel 列顺序**

```python
# tests/test_excel.py
from backend.app.services.storage.job_store import build_result_excel
from backend.app.services.extract.schema import CompanyExtraction
from backend.app.services.extract.fields import FieldDef
import pandas as pd
import io

def test_excel_columns_alternate_with_notes():
    """验证 Excel 列顺序为：字段 + 备注交替"""
    field_defs = [
        FieldDef(
            id="has_hk_entity",
            label="是否有香港主体",
            group="summary",
            col_name="是否有香港主体",
            instruction="测试",
            field_type="yesno",
        ),
    ]
    
    results = [
        CompanyExtraction(
            company_name="测试公司",
            summary={"has_hk_entity": "有"},
            summary_notes={"has_hk_entity": "网页明确提到"},
        )
    ]
    
    excel_bytes = build_result_excel(results, field_defs)
    df = pd.read_excel(io.BytesIO(excel_bytes))
    
    columns = df.columns.tolist()
    assert "企业名称" in columns
    assert "是否有香港主体" in columns
    assert "备注：是否有香港主体" in columns
    
    # 验证顺序：字段后紧跟备注
    hk_idx = columns.index("是否有香港主体")
    note_idx = columns.index("备注：是否有香港主体")
    assert note_idx == hk_idx + 1
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_excel.py::test_excel_columns_alternate_with_notes -v`
Expected: FAIL (备注列不存在)

- [ ] **Step 3: 修改 build_result_excel 函数**

```python
# backend/app/services/storage/job_store.py
def build_result_excel(results: list[CompanyExtraction], field_defs: list[FieldDef]) -> bytes:
    """
    按照本次任务的 field_defs 动态构建 Excel。
    公共列（企业名称/证据条数/来源URL/错误信息）始终包含。
    每个字段后紧跟其备注列。
    """
    rows = []
    for r in results:
        row: dict = {"企业名称": r.company_name}

        # 每个字段后紧跟其备注列
        for fd in field_defs:
            if fd.group == "summary":
                row[fd.col_name] = r.summary.get(fd.id, "")
                row[f"备注：{fd.col_name}"] = r.summary_notes.get(fd.id, "")
            else:  # tags 组（虽然现在为空）
                row[fd.col_name] = r.tags.get(fd.id, "")
                row[f"备注：{fd.col_name}"] = r.tags_notes.get(fd.id, "")

        row["证据条数"] = r.evidence_count
        row["来源URL"]  = " | ".join(r.sources)
        row["错误信息"] = r.error or ""
        rows.append(row)

    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="跨境信息")
    return buf.getvalue()
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_excel.py::test_excel_columns_alternate_with_notes -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/storage/job_store.py tests/test_excel.py
git commit -m "feat(excel): add notes columns alternating with field columns"
```

---

## Task 9: 前端字段面板适配（删除标签维度分组）

**Files:**
- Modify: `frontend/app.js:99-118`
- Modify: `frontend/index.html:106-145`

- [ ] **Step 1: 修改 app.js 的 refreshFieldPanel 函数**

删除标签维度的渲染逻辑，只保留总结维度。

- [ ] **Step 2: 修改 index.html 删除标签字段组**

删除标签维度相关的 HTML 块。

- [ ] **Step 3: 测试前端字段面板显示**

Run: `uvicorn backend.app.main:app --reload --port 8000`
Open: http://localhost:8000
Expected: 字段配置面板只显示"总结维度"和"自定义字段"

- [ ] **Step 4: Commit**

```bash
git add frontend/app.js frontend/index.html
git commit -m "feat(frontend): remove tags dimension from field panel"
```

---

## Task 10: 前端企业详情展示备注

**Files:**
- Modify: `frontend/app.js`
- Modify: `frontend/styles.css`

- [ ] **Step 1: 在 app.js 中添加备注显示逻辑**

在企业详情渲染函数中添加备注显示。

- [ ] **Step 2: 在 styles.css 中添加备注样式**

添加 .field-note 相关样式。

- [ ] **Step 3: 测试前端备注显示**

Run: `uvicorn backend.app.main:app --reload --port 8000`
Expected: 企业详情展开后显示备注信息

- [ ] **Step 4: Commit**

```bash
git add frontend/app.js frontend/styles.css
git commit -m "feat(frontend): add notes display in company detail view"
```

---

## Task 11: 端到端集成测试

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: 创建集成测试验证字段数量和 Excel 导出**

- [ ] **Step 2: 运行集成测试**

Run: `pytest tests/test_integration.py -v`
Expected: PASS

- [ ] **Step 3: 手动端到端测试**

验证完整流程：上传 Excel → 处理 → 下载结果

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add end-to-end integration tests"
```

---

## Task 12: 更新 README 文档

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 更新输出 Excel 列说明**

更新为 10 个字段 + 10 个备注 + 3 个公共列。

- [ ] **Step 2: 更新抽取字段说明**

说明新的字段结构和备注系统。

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README with new field structure"
```

---

## Task 13: 最终验证和清理

- [ ] **Step 1: 运行所有测试**

Run: `pytest tests/ -v`
Expected: 所有测试 PASS

- [ ] **Step 2: 手动完整流程测试**

验证 10 家企业的完整处理流程。

- [ ] **Step 3: 创建最终提交**

```bash
git add -A
git commit -m "feat: complete field optimization implementation"
```

---

## Execution Handoff

Plan complete and saved. Two execution options:

**1. Subagent-Driven (recommended)** - Fresh subagent per task, review between tasks

**2. Inline Execution** - Execute in this session using executing-plans

Which approach?

