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
