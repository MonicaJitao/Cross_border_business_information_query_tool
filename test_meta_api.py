#!/usr/bin/env python3
"""测试 /api/meta 端点返回的数据"""
import requests
import json

try:
    resp = requests.get("http://127.0.0.1:8000/api/meta", timeout=5)
    print(f"状态码: {resp.status_code}")
    print(f"\n响应内容:")
    data = resp.json()
    print(json.dumps(data, indent=2, ensure_ascii=False))
    
    # 检查 field_catalog
    if "field_catalog" in data:
        print(f"\n字段目录数量: {len(data['field_catalog'])}")
        if data['field_catalog']:
            print(f"第一个字段示例: {data['field_catalog'][0]}")
        else:
            print("⚠️ 警告: field_catalog 是空的!")
    else:
        print("⚠️ 警告: 响应中没有 field_catalog!")
        
except requests.exceptions.ConnectionError:
    print("❌ 错误: 无法连接到服务器,请确认后端是否在运行")
except Exception as e:
    print(f"❌ 错误: {e}")
