from backend.app.services.extract.prompt import SYSTEM_PROMPT, _build_json_schema_block, build_user_prompt
from backend.app.services.extract.fields import FieldDef

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
