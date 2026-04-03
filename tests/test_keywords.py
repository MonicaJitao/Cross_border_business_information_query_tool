from backend.app.services.pipeline.keywords import build_keyword_groups, _short_name


# ── short_name 提取 ──────────────────────────────────────────

def test_short_name_basic():
    assert _short_name("深圳市鹏润米业有限公司") == "鹏润米业"

def test_short_name_province_city():
    assert _short_name("广东省深圳市思桅电子有限公司") == "思桅电子"

def test_short_name_stock():
    assert _short_name("广东游盟科技股份有限公司") == "游盟科技"

def test_short_name_group():
    assert _short_name("上海复星医药集团") == "复星医药"

def test_short_name_no_prefix():
    assert _short_name("华为技术有限公司") == "华为技术"


# ── keyword groups ───────────────────────────────────────────

def test_keyword_groups_count():
    """验证关键词组数量为 4"""
    groups = build_keyword_groups("测试公司")
    assert len(groups) == 4

def test_group1_business_info():
    """第 1 组：工商基本面"""
    group = build_keyword_groups("测试公司")[0]
    assert "测试公司" in group
    assert "工商信息" in group
    assert "营收" in group
    assert "年报" in group

def test_group2_overseas_entity():
    """第 2 组：境外主体 / 股权架构"""
    group = build_keyword_groups("深圳市鹏润米业有限公司")[1]
    assert "深圳市鹏润米业有限公司" in group
    assert "鹏润米业" in group
    assert "香港子公司" in group
    assert "VIE架构" in group

def test_group3_import_export():
    """第 3 组：进出口贸易"""
    group = build_keyword_groups("测试公司")[2]
    assert "测试公司" in group
    assert "进出口" in group
    assert "跨境电商" in group

def test_group4_going_overseas():
    """第 4 组：出海国际化"""
    group = build_keyword_groups("测试公司")[3]
    assert "测试公司" in group
    assert "出海" in group
    assert "国际化战略" in group
    assert "全球化" in group
