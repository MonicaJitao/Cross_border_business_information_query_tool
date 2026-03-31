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
