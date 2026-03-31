"""
为每家企业生成 2 组搜索关键词。
第 1 组信息密度最高（境外主体 + 进出口），第 2 组补充细节（出海规划 + 营收行业）。
"""

MIN_RESULTS_TO_SKIP = 5  # 保留此常量，虽然现在不跳过


def build_keyword_groups(company_name: str) -> list[str]:
    """返回有序的 2 组查询字符串。优先度从高到低。"""
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
