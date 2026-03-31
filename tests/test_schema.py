from backend.app.services.extract.schema import CompanyExtraction

def test_company_extraction_with_notes():
    extraction = CompanyExtraction(
        company_name="测试公司",
        summary={"has_hk_entity": "有"},
        summary_notes={"has_hk_entity": "网页明确提到在香港有子公司"},
    )
    assert extraction.summary_notes["has_hk_entity"] == "网页明确提到在香港有子公司"
    assert extraction.tags_notes == {}
