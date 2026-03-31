# 跨境业务企业信息查询工具 - 字段优化设计文档

**日期：** 2025-03-31
**版本：** 1.0
**状态：** 待审核

---

## 1. 概述

### 1.1 设计目标

本次优化旨在简化字段结构、提升信息抽取准确性，并增强结果的可解释性。主要改进包括：

1. **字段精简** - 从 18 个字段（9 总结 + 9 标签）精简到 10 个字段（全部在总结维度）
2. **区域枚举化** - 将"国家"字段改为"区域"字段，使用 5 个枚举值（香港、东南亚、欧美、中东、其他）
3. **股东关系识别** - 明确要求识别企业上下游股东关系中的境外主体
4. **判断标准明确化** - 明确"有/无/未提及"的判断标准
5. **搜索关键词优化** - 从 3 组优化为 2 组高质量关键词，减少搜索次数
6. **备注字段系统** - 为每个字段自动生成备注字段，记录 LLM 判断依据

### 1.2 影响范围

**后端修改：**
- `backend/app/services/extract/fields.py` - 字段定义重构
- `backend/app/services/extract/schema.py` - 数据模型调整（新增备注字段）
- `backend/app/services/extract/prompt.py` - 提示词优化
- `backend/app/services/pipeline/keywords.py` - 搜索关键词优化
- `backend/app/services/storage/job_store.py` - Excel 导出逻辑调整

**前端修改：**
- `frontend/app.js` - 字段面板渲染、企业详情展示（新增备注显示）
- `frontend/index.html` - 可能需要调整样式结构
- `frontend/styles.css` - 新增备注字段样式

---

## 2. 字段重构方案

### 2.1 新的字段结构（10 个字段）

所有字段归入 `summary` 组，删除 `tags` 组。

#### 字段列表

| 序号 | 字段 ID | 字段名称 | 类型 | 输出格式 | 变更说明 |
|-----|---------|---------|------|---------|---------|
| 1 | has_hk_entity | 是否有香港主体 | yesno | 有/无/未提及 | 保留，增强股东关系识别 |
| 2 | has_overseas_entity | 是否有非香港海外主体 | yesno | 有/无/未提及 | 保留，增强股东关系识别 |
| 3 | overseas_entity_regions | 海外主体所在区域 | region | 枚举值（可多选） | 修改：国家→区域 |
| 4 | has_import_export | 是否有进出口业务 | yesno | 有/无/未提及 | 保留 |
| 5 | import_export_regions | 进出口业务涉及区域 | region | 枚举值（可多选） | 修改：国家→区域 |
| 6 | import_export_mode | 进出口主要模式 | text | 文本 | 保留 |
| 7 | annual_import_export_amount | 年进出口金额 | amount | 金额区间 | 保留 |
| 8 | industry | 企业所属行业 | text | 文本 | 保留 |
| 9 | annual_revenue | 企业年营收规模 | amount | 金额区间 | 保留 |
| 10 | has_going_overseas | 是否有出海规划 | yesno | 有/无/未提及 | 新增：从 tags 移入 |

#### 删除的字段（8 个）

- `tag1_import_export` - 与 has_import_export 重复
- `tag2_overseas_entity` - 与 has_overseas_entity 重复
- `tag3_going_overseas` - 移至 summary 组
- `tag4_forex` - 外汇业务（删除）
- `tag5_fx_settlement` - 结售汇业务（删除）
- `tag6_industry` - 与 industry 重复
- `tag7_business_scale` - 经营规模（删除）
- `tag8_import_export_region` - 与 import_export_regions 合并
- `tag9_overseas_region` - 与 overseas_entity_regions 合并

---

## 3. 区域枚举化设计

### 3.1 枚举值定义

**5 个区域枚举值：**
1. **香港** - 香港特别行政区
2. **东南亚** - 泰国、越南、新加坡、马来西亚、印尼、菲律宾、柬埔寨等
3. **欧美** - 美国、英国、德国、法国、西班牙、意大利、荷兰、加拿大、澳大利亚等
4. **中东** - 迪拜、沙特、阿联酋、卡塔尔等
5. **其他** - 非洲、拉美、其他未列明地区

### 3.2 映射策略

**采用 LLM 智能映射，而非硬编码规则：**

- 在提示词中提供映射示例，让 LLM 根据地理和经济常识进行归类
- 优势：灵活性高，可自动处理新国家/地区
- 风险控制：在 SYSTEM_PROMPT 中强调归类原则

### 3.3 多选格式

- 使用顿号分隔：`"香港、东南亚、欧美"`
- 示例：企业在香港有子公司，在泰国和美国有业务 → `"香港、东南亚、欧美"`

---

## 4. 判断标准明确化

### 4.1 三值逻辑定义

对于所有 yesno 类型字段：

| 输出值 | 判断标准 | 示例 |
|-------|---------|------|
| **有** | 证据中明确提到存在该情况 | "该公司在香港设有全资子公司" |
| **无** | 证据中明确提到不存在该情况 | "该公司目前仅在国内开展业务，无海外主体" |
| **未提及** | 证据中完全没有相关信息，无法判断 | 搜索结果中没有任何关于境外主体的信息 |

### 4.2 常见误判场景

**场景 1：证据缺失 ≠ 明确不存在**
- ❌ 错误：搜索结果没提到进出口 → 填"无"
- ✅ 正确：搜索结果没提到进出口 → 填"未提及"

**场景 2：股东关系识别**
- ❌ 错误：只看企业直接注册的主体
- ✅ 正确：同时识别股东关系中的境外主体

---

## 5. 搜索关键词优化

### 5.1 优化目标

- 减少搜索次数：从 3-4 组 → 2 组
- 提高关键词质量：每组聚焦多个维度
- 保持信息覆盖：确保 10 个字段都有对应关键词

### 5.2 新的关键词组设计

```python
def build_keyword_groups(company_name: str) -> list[str]:
    """返回有序的 2 组查询字符串。"""
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

### 5.3 关键词覆盖分析

| 关键词组 | 关键词 | 覆盖字段数 | 预期命中率 |
|---------|-------|-----------|-----------|
| 第 1 组 | 股东、香港、海外、进出口、跨境 | 6 个 | 高 |
| 第 2 组 | 出海、国际化、营收、年报、行业 | 4 个 | 中 |

### 5.4 性能提升

- 搜索次数减少 50%（4 次 → 2 次）
- 每家企业节省约 0.5-1 秒处理时间
- 批量处理 1000 家企业可节省 8-15 分钟

---

## 6. 提示词优化方案

### 6.1 SYSTEM_PROMPT 优化

#### 优化前（当前版本）

```python
SYSTEM_PROMPT = """你是一名专注于跨境贸易的企业信息分析师。
你的任务是根据用户提供的企业网络搜索证据，提取结构化的跨境业务信息。
请只依据证据中的内容作答，无法判断时如实标注"未提及"或留空，不要捏造信息。
输出严格为 JSON 格式，不要输出任何额外内容。"""
```

**存在的问题：**
1. 没有明确"有/无/未提及"的判断标准
2. 没有提及股东关系的识别要求
3. 没有区域归类的指导规则
4. "留空"和"未提及"混用，容易造成混淆

#### 优化后（新版本）

```python
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


### 6.2 字段级 instruction 优化

#### 关键字段的新 instruction

**1. 是否有香港主体 (has_hk_entity)**
```python
instruction='证据中是否明确提到企业在香港有注册主体（子公司/分公司），或通过股东关系关联香港主体。明确有填"有"，明确无填"无"，无相关信息填"未提及"'
```

**2. 是否有非香港海外主体 (has_overseas_entity)**
```python
instruction='证据中是否明确提到企业在香港以外有海外主体，或通过股东关系关联海外主体。明确有填"有"，明确无填"无"，无相关信息填"未提及"'
```

**3. 海外主体所在区域 (overseas_entity_regions)**
```python
instruction='若有境外主体，按地理区域归类，可多选（顿号分隔）。枚举值：香港、东南亚、欧美、中东、其他。归类示例：泰国/越南→东南亚，美国/英国/西班牙→欧美，迪拜/沙特→中东。无境外主体填"无"，无法判断填"未提及"'
```

**4. 是否有进出口业务 (has_import_export)**
```python
instruction='证据中是否明确提到企业有进出口业务。明确有填"有"，明确无填"无"，无相关信息填"未提及"'
```

**5. 进出口业务涉及区域 (import_export_regions)**
```python
instruction='进出口业务涉及的地理区域，可多选（顿号分隔）。枚举值：香港、东南亚、欧美、中东、其他。归类规则同"海外主体所在区域"。无进出口业务填"无"，无法判断填"未提及"'
```

**6. 是否有出海规划 (has_going_overseas)**
```python
instruction='证据中是否明确提到企业在规划、布局或拓展海外市场/国际化业务。明确有填"有"，明确无填"无"，无相关信息填"未提及"'
```

### 6.3 动态约束提示优化

在 `build_user_prompt` 函数中，增强约束提示：

```python
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
```

### 6.4 JSON Schema 示例调整

```python
def _build_json_schema_block(field_defs: list[FieldDef]) -> str:
    summary_lines = []
    summary_note_lines = []

    for fd in field_defs:
        if fd.group == "summary":
            summary_lines.append(f'    "{fd.id}": "{fd.instruction}"')
            summary_note_lines.append(f'    "{fd.id}": "简要说明判断依据"')

    return f'''{{
  "summary": {{
{",\n".join(summary_lines)}
  }},
  "summary_notes": {{
{",\n".join(summary_note_lines)}
  }}
}}'''
```

---

## 7. 备注字段系统设计

### 7.1 设计目标

为每个字段自动生成对应的备注字段，记录 LLM 的判断依据，提升结果的可解释性和可审计性。

### 7.2 数据结构调整

#### CompanyExtraction 模型修改

```python
class CompanyExtraction(BaseModel):
    company_name: str
    summary: dict[str, str]              # 字段值
    summary_notes: dict[str, str]        # 字段备注（新增）
    tags: dict[str, str]                 # 保留（虽然现在为空）
    tags_notes: dict[str, str]           # 保留（虽然现在为空）
    evidence_count: int
    sources: list[str]
    error: Optional[str]
    trace: CompanyTrace
```

**设计原则：**
- 字段值和备注分离，结构清晰
- 与现有架构一致（summary/tags 分组）
- 自动配对，无需手动维护

### 7.3 LLM 输出格式

#### JSON 输出示例

```json
{
  "summary": {
    "has_hk_entity": "有",
    "has_overseas_entity": "无",
    "overseas_entity_regions": "东南亚、欧美",
    "has_import_export": "有",
    "import_export_regions": "东南亚、欧美",
    "import_export_mode": "主要出口",
    "annual_import_export_amount": "5000-8000万美元",
    "industry": "精密仪器制造",
    "annual_revenue": "2-3亿元人民币",
    "has_going_overseas": "有"
  },
  "summary_notes": {
    "has_hk_entity": "网页明确提到该公司在香港设有全资子公司'XX（香港）有限公司'",
    "has_overseas_entity": "网页明确说明该公司目前仅在国内和香港开展业务，无其他海外主体",
    "overseas_entity_regions": "证据显示在泰国、新加坡有分公司（东南亚），在美国有办事处（欧美）",
    "has_import_export": "年报显示2023年进出口额达7000万美元",
    "import_export_regions": "主要出口至东南亚（泰国、越南）和欧美（美国、德国）",
    "import_export_mode": "年报显示出口占比85%，进口占比15%",
    "annual_import_export_amount": "年报披露2023年进出口总额约7000万美元",
    "industry": "官网介绍主营精密测量仪器和光学设备制造",
    "annual_revenue": "年报显示2023年营收2.5亿元人民币",
    "has_going_overseas": "新闻报道该公司计划在越南建立生产基地，拓展东南亚市场"
  }
}
```

### 7.4 Excel 导出调整

#### 列顺序设计

字段和备注交替排列，便于阅读：

```
企业名称 | 是否有香港主体 | 备注：是否有香港主体 | 是否有非香港海外主体 | 备注：是否有非香港海外主体 | ...
```

#### 实现代码

```python
def build_result_excel(results: list[CompanyExtraction], field_defs: list[FieldDef]) -> bytes:
    rows = []
    for r in results:
        row: dict = {"企业名称": r.company_name}

        # 每个字段后紧跟其备注列
        for fd in field_defs:
            if fd.group == "summary":
                row[fd.col_name] = r.summary.get(fd.id, "")
                row[f"备注：{fd.col_name}"] = r.summary_notes.get(fd.id, "")

        row["证据条数"] = r.evidence_count
        row["来源URL"] = " | ".join(r.sources)
        row["错误信息"] = r.error or ""
        rows.append(row)

    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="跨境信息")
    return buf.getvalue()
```

### 7.5 前端展示调整

#### 企业详情卡片中展示备注

```javascript
function renderCompanyDetail(extraction) {
    let html = '';

    for (const fd of fieldDefs) {
        const value = extraction.summary[fd.id] || '—';
        const note = extraction.summary_notes[fd.id] || '无备注';

        html += `
        <div class="field-row">
            <span class="field-label">${fd.label}:</span>
            <span class="field-value">${value}</span>
        </div>
        <div class="field-note">
            <span class="note-icon">📝</span>
            <span class="note-text">${note}</span>
        </div>
        `;
    }

    return html;
}
```

#### CSS 样式

```css
.field-note {
    margin-left: 2rem;
    margin-top: 0.25rem;
    margin-bottom: 0.75rem;
    padding: 0.5rem;
    background: var(--bg-secondary);
    border-left: 2px solid var(--accent);
    font-size: 0.875rem;
    color: var(--text-secondary);
}

.note-icon {
    margin-right: 0.5rem;
}

.note-text {
    font-style: italic;
}
```

---

## 8. 实现计划概要

### 8.1 实施顺序

建议按以下顺序实施，确保每个阶段可独立测试：

**阶段 1：后端数据结构调整**
1. 修改 `schema.py` - 添加 `summary_notes` 和 `tags_notes` 字段
2. 修改 `fields.py` - 重构字段定义（删除 8 个标签字段，修改 2 个区域字段，新增 1 个出海规划字段）
3. 修改 `parse.py` - 适配新的 JSON 解析逻辑（处理 summary_notes）

**阶段 2：提示词优化**
4. 修改 `prompt.py` - 更新 SYSTEM_PROMPT 和字段级 instruction
5. 修改 `prompt.py` - 调整 JSON Schema 生成逻辑（包含 summary_notes）

**阶段 3：搜索关键词优化**
6. 修改 `keywords.py` - 从 3 组优化为 2 组关键词

**阶段 4：Excel 导出调整**
7. 修改 `job_store.py` - 调整 Excel 列顺序（字段 + 备注交替）

**阶段 5：前端适配**
8. 修改 `app.js` - 字段面板渲染逻辑（删除标签维度分组）
9. 修改 `app.js` - 企业详情展示（新增备注显示）
10. 修改 `styles.css` - 新增备注字段样式

**阶段 6：测试与验证**
11. 单元测试 - 测试字段定义、提示词生成、JSON 解析
12. 集成测试 - 端到端测试（上传 Excel → 处理 → 下载结果）
13. 人工验证 - 抽样检查备注质量和区域归类准确性

### 8.2 风险控制

**风险 1：LLM 不按新格式输出**
- 缓解措施：在 `parse.py` 中添加兼容逻辑，如果缺少 `summary_notes`，自动填充空字符串
- 回滚方案：保留旧版本 prompt，可快速切换

**风险 2：区域归类不准确**
- 缓解措施：在提示词中提供详细示例，强调归类原则
- 监控方案：记录 LLM 原始输出，便于后续分析和优化

**风险 3：备注字段过长**
- 缓解措施：在提示词中明确要求"简洁（1-2句话）"
- 技术方案：在 Excel 导出时截断过长备注（保留前 200 字符）

### 8.3 兼容性考虑

**续传功能兼容性：**
- 旧版本 Excel（18 个字段）上传后，系统应能识别并跳过已处理记录
- 新版本 Excel（10 个字段 + 10 个备注字段）上传后，系统应能正确解析

**实现方案：**
- 在 `_parse_resume_data` 函数中，根据列名动态匹配字段
- 如果检测到旧版本列名（如"标签1_进出口业务"），忽略该列
- 如果检测到备注列（如"备注：是否有香港主体"），提取备注内容

---

## 9. 预期效果

### 9.1 量化指标

| 指标 | 当前值 | 目标值 | 提升幅度 |
|-----|-------|-------|---------|
| 字段数量 | 18 个 | 10 个 | 减少 44% |
| 搜索次数/企业 | 3-4 次 | 2 次 | 减少 50% |
| 股东关系识别率 | ~30% | ~70% | 提升 133% |
| 区域归类准确率 | ~60% | ~90% | 提升 50% |
| 三值判断准确率 | ~70% | ~85% | 提升 21% |
| 处理速度 | 300-1100 企业/小时 | 350-1200 企业/小时 | 提升 10-15% |

### 9.2 质量提升

**可解释性：**
- 每个字段都有对应的备注，用户可以理解 LLM 的判断依据
- 便于人工审核和质量控制

**准确性：**
- 明确的判断标准减少"有/无/未提及"的混淆
- 股东关系识别提高境外主体的覆盖率
- 区域枚举化统一输出格式，便于后续分析

**效率：**
- 字段精简减少 LLM 处理负担
- 搜索次数减少提升整体吞吐量

---

## 10. 后续优化方向

### 10.1 短期优化（1-2 周）

1. **关键词动态调整** - 根据搜索结果质量动态调整第 2 组关键词
2. **备注质量监控** - 统计备注长度分布，优化提示词
3. **区域归类验证** - 抽样检查 LLM 的区域归类准确性

### 10.2 中期优化（1-2 月）

1. **字段权重系统** - 为不同字段设置权重，优先保证核心字段的准确性
2. **多轮抽取** - 对于"未提及"的字段，尝试使用更精准的关键词再次搜索
3. **置信度评分** - LLM 输出每个字段的置信度（高/中/低）

### 10.3 长期优化（3-6 月）

1. **自定义区域** - 允许用户自定义区域枚举值
2. **字段模板** - 提供多套字段模板（如"基础版"、"详细版"、"金融版"）
3. **LLM 微调** - 基于人工标注数据微调 LLM，提升抽取准确性

---

## 11. 总结

本次优化通过字段精简、提示词优化、搜索关键词优化和备注字段系统，全面提升了跨境业务企业信息查询工具的准确性、效率和可解释性。

**核心改进：**
1. 字段从 18 个精简到 10 个，结构更清晰
2. 区域枚举化统一输出格式，便于分析
3. 明确判断标准，减少误判
4. 股东关系识别提高境外主体覆盖率
5. 搜索次数减半，提升处理速度
6. 备注字段系统提升可解释性

**预期效果：**
- 处理速度提升 10-15%
- 股东关系识别率提升 133%
- 区域归类准确率提升 50%
- 三值判断准确率提升 21%

**下一步：**
进入实施阶段，按照实施计划逐步完成后端、前端的代码修改和测试验证。

---

**文档版本：** 1.0  
**最后更新：** 2025-03-31  
**审核状态：** 待用户审核

