#!/usr/bin/env python3
"""检查环境变量加载情况"""
import os
from pathlib import Path

print("=== 环境变量加载诊断 ===\n")

# 检查 .env 文件是否存在
env_path = Path(".env")
print(f"1. 检查 .env 文件:")
print(f"   路径: {env_path.absolute()}")
print(f"   是否存在: {env_path.exists()}")

if env_path.exists():
    print(f"   文件大小: {env_path.stat().st_size} 字节")
    print(f"\n2. .env 文件内容:")
    with open(env_path, encoding='utf-8') as f:
        lines = f.readlines()
        for i, line in enumerate(lines, 1):
            if 'VOLCENGINE' in line.upper():
                print(f"   第 {i} 行: {line.rstrip()}")

print(f"\n3. 直接从操作系统环境变量读取:")
volcengine_key_from_os = os.getenv("VOLCENGINE_API_KEY")
print(f"   VOLCENGINE_API_KEY = {volcengine_key_from_os}")

print(f"\n4. 通过 pydantic-settings 读取:")
try:
    from backend.app.core.config import settings
    print(f"   settings.volcengine_api_key = {settings.volcengine_api_key}")
    
    if settings.volcengine_api_key:
        print(f"   ✓ 火山引擎 API Key 已加载")
        print(f"   Key 长度: {len(settings.volcengine_api_key)}")
        print(f"   Key 预览: {settings.volcengine_api_key[:20]}...")
    else:
        print(f"   ✗ 火山引擎 API Key 为空")
        
    print(f"\n5. 检查其他配置（对比）:")
    print(f"   settings.metaso_api_key = {'有值' if settings.metaso_api_key else '无'}")
    print(f"   settings.baidu_api_key = {'有值' if settings.baidu_api_key else '无'}")
    
except Exception as e:
    print(f"   ✗ 加载失败: {e}")

print("\n6. 检查 Settings 类的配置:")
try:
    from backend.app.core.config import Settings
    import inspect
    source = inspect.getsource(Settings)
    print("   Settings 类定义:")
    for line in source.split('\n'):
        if 'volcengine' in line.lower():
            print(f"   {line}")
except Exception as e:
    print(f"   ✗ 无法读取: {e}")
