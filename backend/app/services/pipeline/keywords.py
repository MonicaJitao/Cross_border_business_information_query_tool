"""
为每家企业生成 4 组搜索关键词，分别覆盖工商信息、境外主体、进出口、出海国际化。
"""

import re


def _short_name(company_name: str) -> str:
    """提取公司简称：去除地名前缀和'(股份)有限公司/集团'后缀。"""
    name = re.sub(r'^(.*?[省市区县])+', '', company_name)
    name = re.sub(r'(股份)?有限公司$', '', name).strip()
    name = re.sub(r'集团$', '', name).strip()
    return name


def build_keyword_groups(company_name: str) -> list[str]:
    """返回有序的 4 组查询字符串。"""
    short = _short_name(company_name)
    return [
        # 第 1 组：工商基本面
        f"{company_name} 工商信息 行业 营收 注册资本 年报",
        # 第 2 组：境外主体 / 股权架构
        f'"{company_name}" OR "{short}" 香港子公司 OR 港资 OR 海外主体 OR 实际控制人 OR VIE架构 OR 开曼 OR BVI',
        # 第 3 组：进出口贸易
        f"{company_name} 进出口 外贸 出口国家 跨境电商 海关",
        # 第 4 组：出海国际化
        f"{company_name} 出海 国际化战略 海外布局 全球化",
    ]
