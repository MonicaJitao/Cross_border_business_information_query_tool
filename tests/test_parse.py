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


def test_parse_json_with_unescaped_quotes():
    """验证能修复 LLM 输出中未转义的双引号"""
    # 模拟 LLM 在备注中输出未转义的中文引号（ASCII "）
    llm_output = '''```json
{
  "summary": {
    "has_import_export": "有"
  },
  "summary_notes": {
    "has_import_export": "证据显示其经营范围明确包含"技术进出口"和"货物进出口"，表明该公司已登记具备进出口业务资质。"
  }
}
```'''

    parsed, strategy = parse_llm_json(llm_output)
    assert parsed is not None, "应该能解析包含未转义引号的 JSON"
    assert strategy == "repair_quotes"
    assert parsed["summary"]["has_import_export"] == "有"
    assert "技术进出口" in parsed["summary_notes"]["has_import_export"]


def test_parse_json_with_multiple_unescaped_quotes():
    """验证能修复多处未转义引号"""
    llm_output = '''{
  "summary": {
    "has_hk_entity": "无",
    "has_going_overseas": "有"
  },
  "summary_notes": {
    "has_hk_entity": "未找到"香港子公司"相关记录。",
    "has_going_overseas": "证据提及"游戏出海"和"跨平台"业务。"
  }
}'''

    parsed, strategy = parse_llm_json(llm_output)
    assert parsed is not None, "应该能修复多处未转义引号"
    assert parsed["summary"]["has_hk_entity"] == "无"
    assert "香港子公司" in parsed["summary_notes"]["has_hk_entity"]
    assert "游戏出海" in parsed["summary_notes"]["has_going_overseas"]
