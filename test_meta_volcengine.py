#!/usr/bin/env python3
"""测试 /api/meta 接口返回的火山引擎配置"""
import requests
import json

try:
    resp = requests.get("http://127.0.0.1:8000/api/meta", timeout=5)
    data = resp.json()
    
    print("=== /api/meta 接口响应分析 ===\n")
    
    # 查找火山引擎配置
    for provider in data.get("search_providers", []):
        if provider.get("id") == "volcengine":
            print(f"火山引擎搜索配置:")
            print(f"  id: {provider.get('id')}")
            print(f"  name: {provider.get('name')}")
            print(f"  has_preset_key: {provider.get('has_preset_key')}")
            print()
            
            if provider.get('has_preset_key'):
                print("✓ 前端应该显示'后端已预置'徽章")
            else:
                print("✗ 前端不会显示'后端已预置'徽章")
                print("   原因: has_preset_key 为 False")
            break
    else:
        print("✗ 未找到火山引擎配置")
        
    print("\n完整响应:")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    
except Exception as e:
    print(f"✗ 错误: {e}")
