"""
为每家企业生成 3 组搜索关键词。
第 1 组信息密度最高（官网/年报/进出口），后续组补充细节。
逐步加码策略：第 1 组搜索有效结果 >= MIN_RESULTS_TO_SKIP 时跳过后两组。
"""

MIN_RESULTS_TO_SKIP = 5  # 命中阈值：结果数 >= 此值则跳过后续关键词组


def build_keyword_groups(company_name: str) -> list[str]:
    """返回有序的 3 组查询字符串。优先度从高到低。"""
    return [
        f"{company_name} 进出口 跨境贸易 海关",
        f"{company_name} 香港 境外主体 贸易公司",
        f"{company_name} 营收 主营业务 产品",
    ]
