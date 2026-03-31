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
