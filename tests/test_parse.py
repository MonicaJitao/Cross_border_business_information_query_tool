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
