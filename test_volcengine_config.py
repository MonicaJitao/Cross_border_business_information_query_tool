#!/usr/bin/env python3
"""测试火山引擎配置验证"""
import json
from backend.app.api.jobs import JobConfig, SearchProviderConfig

# 模拟前端提交的配置（仅火山引擎）
test_config_volcengine_only = {
    "search_providers": [
        {
            "id": "volcengine",
            "num_results": 10,
            "api_key": None  # 使用后端预置 Key
        }
    ],
    "field_defs": [
        {
            "id": "has_hk_entity",
            "label": "是否有香港主体",
            "group": "summary",
            "col_name": "是否有香港主体",
            "instruction": "测试",
            "field_type": "yesno"
        }
    ],
    "llm": {
        "provider": "deepseek_official",
        "base_url": None,
        "api_key": None,
        "model": None
    },
    "concurrency": {
        "search": 5,
        "llm": 3
    }
}

# 模拟前端提交的配置（秘塔 + 火山引擎）
test_config_mixed = {
    "search_providers": [
        {
            "id": "metaso",
            "num_results": 10,
            "api_key": None
        },
        {
            "id": "volcengine",
            "num_results": 10,
            "api_key": None
        }
    ],
    "field_defs": [
        {
            "id": "has_hk_entity",
            "label": "是否有香港主体",
            "group": "summary",
            "col_name": "是否有香港主体",
            "instruction": "测试",
            "field_type": "yesno"
        }
    ],
    "llm": {
        "provider": "deepseek_official",
        "base_url": None,
        "api_key": None,
        "model": None
    },
    "concurrency": {
        "search": 5,
        "llm": 3
    }
}

print("=== 测试 1: 仅火山引擎 ===")
try:
    cfg1 = JobConfig(**test_config_volcengine_only)
    print("✓ 配置验证通过")
    print(f"  搜索源数量: {len(cfg1.search_providers)}")
    for prov in cfg1.search_providers:
        print(f"  - {prov.id}: {prov.num_results}条, api_key={'有' if prov.api_key else '无'}")
except Exception as e:
    print(f"✗ 配置验证失败: {e}")

print("\n=== 测试 2: 秘塔 + 火山引擎 ===")
try:
    cfg2 = JobConfig(**test_config_mixed)
    print("✓ 配置验证通过")
    print(f"  搜索源数量: {len(cfg2.search_providers)}")
    for prov in cfg2.search_providers:
        print(f"  - {prov.id}: {prov.num_results}条, api_key={'有' if prov.api_key else '无'}")
except Exception as e:
    print(f"✗ 配置验证失败: {e}")

print("\n=== 检查环境变量中的火山引擎 API Key ===")
from backend.app.core.config import settings
if settings.volcengine_api_key:
    key_preview = settings.volcengine_api_key[:20] + "..." if len(settings.volcengine_api_key) > 20 else settings.volcengine_api_key
    print(f"✓ 火山引擎 API Key 已配置: {key_preview}")
else:
    print("✗ 火山引擎 API Key 未配置")
