"""
端到端集成测试。

验证完整流程：
1. 字段定义数量正确（10 个 summary，0 个 tags）
2. Excel 导出包含备注列
3. 完整抽取流程工作正常
"""
import io
import pandas as pd
import pytest
from backend.app.services.extract.fields import (
    ALL_BUILTIN_FIELDS,
    SUMMARY_FIELDS,
    TAGS_FIELDS,
    FieldDef,
)
from backend.app.services.extract.schema import CompanyExtraction
from backend.app.services.storage.job_store import build_result_excel


class TestFieldDefinitions:
    """测试字段定义"""

    def test_field_count_is_correct(self):
        """验证字段总数为 10 个"""
        assert len(ALL_BUILTIN_FIELDS) == 10, "内置字段总数应为 10 个"
        assert len(SUMMARY_FIELDS) == 10, "summary 字段应为 10 个"
        assert len(TAGS_FIELDS) == 0, "tags 字段应为 0 个"

    def test_all_fields_are_summary_group(self):
        """验证所有字段都在 summary 组"""
        for field in ALL_BUILTIN_FIELDS:
            assert field.group == "summary", f"字段 {field.id} 应在 summary 组"

    def test_field_structure_is_valid(self):
        """验证每个字段的结构完整"""
        for field in ALL_BUILTIN_FIELDS:
            assert field.id, f"字段缺少 id"
            assert field.label, f"字段 {field.id} 缺少 label"
            assert field.col_name, f"字段 {field.id} 缺少 col_name"
            assert field.instruction, f"字段 {field.id} 缺少 instruction"
            assert field.field_type in ["yesno", "text", "region", "amount"], \
                f"字段 {field.id} 的 field_type 无效"


class TestExcelExport:
    """测试 Excel 导出功能"""

    def test_excel_includes_notes_columns(self):
        """验证 Excel 包含备注列"""
        field_defs = [
            FieldDef(
                id="has_hk_entity",
                label="是否有香港主体",
                group="summary",
                col_name="是否有香港主体",
                instruction="测试",
                field_type="yesno",
            ),
            FieldDef(
                id="industry",
                label="企业所属行业",
                group="summary",
                col_name="企业所属行业",
                instruction="测试",
                field_type="text",
            ),
        ]

        results = [
            CompanyExtraction(
                company_name="测试公司A",
                summary={
                    "has_hk_entity": "有",
                    "industry": "跨境电商",
                },
                summary_notes={
                    "has_hk_entity": "官网明确提到香港子公司",
                    "industry": "主营跨境电商业务",
                },
                evidence_count=5,
                sources=["https://example.com"],
            )
        ]

        excel_bytes = build_result_excel(results, field_defs)
        df = pd.read_excel(io.BytesIO(excel_bytes))

        columns = df.columns.tolist()

        # 验证基础列存在
        assert "企业名称" in columns
        assert "证据条数" in columns
        assert "来源URL" in columns
        assert "错误信息" in columns

        # 验证字段列和备注列都存在
        assert "是否有香港主体" in columns
        assert "备注：是否有香港主体" in columns
        assert "企业所属行业" in columns
        assert "备注：企业所属行业" in columns

    def test_excel_notes_follow_fields(self):
        """验证备注列紧跟在字段列后面"""
        field_defs = SUMMARY_FIELDS[:3]  # 取前 3 个字段测试

        results = [
            CompanyExtraction(
                company_name="测试公司",
                summary={fd.id: "测试值" for fd in field_defs},
                summary_notes={fd.id: "测试备注" for fd in field_defs},
            )
        ]

        excel_bytes = build_result_excel(results, field_defs)
        df = pd.read_excel(io.BytesIO(excel_bytes))

        columns = df.columns.tolist()

        # 验证每个字段后紧跟其备注列
        for fd in field_defs:
            field_idx = columns.index(fd.col_name)
            note_col = f"备注：{fd.col_name}"
            note_idx = columns.index(note_col)
            assert note_idx == field_idx + 1, \
                f"{note_col} 应紧跟在 {fd.col_name} 后面"

    def test_excel_with_all_builtin_fields(self):
        """验证使用所有内置字段导出 Excel"""
        results = [
            CompanyExtraction(
                company_name="完整测试公司",
                summary={
                    "has_hk_entity": "有",
                    "has_overseas_entity": "有",
                    "overseas_entity_regions": "香港、东南亚",
                    "has_import_export": "有",
                    "import_export_regions": "欧美、东南亚",
                    "import_export_mode": "进出口都有",
                    "annual_import_export_amount": "3-4亿元人民币",
                    "has_going_overseas": "有",
                    "industry": "精密仪器制造",
                    "annual_revenue": "2000-3500万元人民币",
                },
                summary_notes={
                    "has_hk_entity": "官网提到香港分公司",
                    "has_overseas_entity": "在新加坡有子公司",
                    "overseas_entity_regions": "香港和新加坡",
                    "has_import_export": "年报显示有进出口业务",
                    "import_export_regions": "主要面向欧美和东南亚市场",
                    "import_export_mode": "既有进口原材料也有出口产品",
                    "annual_import_export_amount": "根据年报数据",
                    "has_going_overseas": "计划拓展中东市场",
                    "industry": "主营精密仪器",
                    "annual_revenue": "2023年年报",
                },
                evidence_count=10,
                sources=["https://example.com/1", "https://example.com/2"],
            )
        ]

        excel_bytes = build_result_excel(results, ALL_BUILTIN_FIELDS)
        df = pd.read_excel(io.BytesIO(excel_bytes))

        # 验证所有字段都在 Excel 中
        columns = df.columns.tolist()
        for field in ALL_BUILTIN_FIELDS:
            assert field.col_name in columns, f"缺少字段列: {field.col_name}"
            note_col = f"备注：{field.col_name}"
            assert note_col in columns, f"缺少备注列: {note_col}"

        # 验证数据正确写入
        assert df.iloc[0]["企业名称"] == "完整测试公司"
        assert df.iloc[0]["是否有香港主体"] == "有"
        assert df.iloc[0]["备注：是否有香港主体"] == "官网提到香港分公司"
        assert df.iloc[0]["证据条数"] == 10


class TestExtractionSchema:
    """测试抽取结果数据模型"""

    def test_extraction_with_summary_and_notes(self):
        """验证 summary 和 summary_notes 正常工作"""
        extraction = CompanyExtraction(
            company_name="测试公司",
            summary={
                "has_hk_entity": "有",
                "industry": "跨境电商",
            },
            summary_notes={
                "has_hk_entity": "官网明确提到",
                "industry": "主营业务",
            },
        )

        assert extraction.company_name == "测试公司"
        assert extraction.summary["has_hk_entity"] == "有"
        assert extraction.summary["industry"] == "跨境电商"
        assert extraction.summary_notes["has_hk_entity"] == "官网明确提到"
        assert extraction.summary_notes["industry"] == "主营业务"

    def test_extraction_tags_are_empty(self):
        """验证 tags 字段为空（当前版本无 tags 字段）"""
        extraction = CompanyExtraction(
            company_name="测试公司",
            summary={"has_hk_entity": "有"},
        )

        assert extraction.tags == {}
        assert extraction.tags_notes == {}

    def test_extraction_with_error(self):
        """验证错误处理"""
        extraction = CompanyExtraction(
            company_name="错误公司",
            error="搜索失败",
        )

        assert extraction.error == "搜索失败"
        assert extraction.summary == {}
        assert extraction.summary_notes == {}


class TestEndToEndFlow:
    """测试端到端流程"""

    def test_complete_flow_with_multiple_companies(self):
        """验证多公司完整流程"""
        # 模拟 3 家公司的抽取结果
        results = [
            CompanyExtraction(
                company_name="公司A",
                summary={
                    "has_hk_entity": "有",
                    "industry": "跨境电商",
                },
                summary_notes={
                    "has_hk_entity": "有香港子公司",
                    "industry": "电商行业",
                },
                evidence_count=5,
                sources=["https://a.com"],
            ),
            CompanyExtraction(
                company_name="公司B",
                summary={
                    "has_hk_entity": "无",
                    "has_import_export": "有",
                },
                summary_notes={
                    "has_hk_entity": "未提及香港主体",
                    "has_import_export": "有进出口业务",
                },
                evidence_count=3,
                sources=["https://b.com"],
            ),
            CompanyExtraction(
                company_name="公司C",
                error="搜索失败",
                evidence_count=0,
                sources=[],
            ),
        ]

        # 使用部分字段
        field_defs = [
            fd for fd in ALL_BUILTIN_FIELDS
            if fd.id in ["has_hk_entity", "industry", "has_import_export"]
        ]

        # 生成 Excel
        excel_bytes = build_result_excel(results, field_defs)
        df = pd.read_excel(io.BytesIO(excel_bytes))

        # 验证行数
        assert len(df) == 3

        # 验证公司A
        row_a = df[df["企业名称"] == "公司A"].iloc[0]
        assert row_a["是否有香港主体"] == "有"
        assert row_a["备注：是否有香港主体"] == "有香港子公司"
        assert row_a["企业所属行业"] == "跨境电商"
        assert row_a["证据条数"] == 5

        # 验证公司B
        row_b = df[df["企业名称"] == "公司B"].iloc[0]
        assert row_b["是否有香港主体"] == "无"
        assert row_b["是否有进出口业务"] == "有"

        # 验证公司C（错误情况）
        row_c = df[df["企业名称"] == "公司C"].iloc[0]
        assert row_c["错误信息"] == "搜索失败"
        assert row_c["证据条数"] == 0

    def test_field_selection_affects_output(self):
        """验证字段选择影响输出列"""
        results = [
            CompanyExtraction(
                company_name="测试公司",
                summary={
                    "has_hk_entity": "有",
                    "industry": "制造业",
                    "has_import_export": "有",
                },
                summary_notes={
                    "has_hk_entity": "备注1",
                    "industry": "备注2",
                    "has_import_export": "备注3",
                },
            )
        ]

        # 只选择 2 个字段
        selected_fields = [
            fd for fd in ALL_BUILTIN_FIELDS
            if fd.id in ["has_hk_entity", "industry"]
        ]

        excel_bytes = build_result_excel(results, selected_fields)
        df = pd.read_excel(io.BytesIO(excel_bytes))

        columns = df.columns.tolist()

        # 验证选中的字段在输出中
        assert "是否有香港主体" in columns
        assert "备注：是否有香港主体" in columns
        assert "企业所属行业" in columns
        assert "备注：企业所属行业" in columns

        # 验证未选中的字段不在输出中
        assert "是否有进出口业务" not in columns
        assert "备注：是否有进出口业务" not in columns
