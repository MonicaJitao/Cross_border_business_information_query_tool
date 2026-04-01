#!/usr/bin/env python3
"""直接测试环境变量读取"""
import os
from pathlib import Path

# 设置工作目录
os.chdir(Path(__file__).parent)

print("=== 直接测试 .env 文件读取 ===\n")

# 方法1: 使用 python-dotenv 直接读取
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
    print("1. 使用 python-dotenv 读取:")
    print(f"   METASO_API_KEY: {os.getenv('METASO_API_KEY', 'NOT_FOUND')[:30]}...")
    print(f"   BAIDU_API_KEY: {os.getenv('BAIDU_API_KEY', 'NOT_FOUND')[:30]}...")
    print(f"   VOLCENGINE_API_KEY: {os.getenv('VOLCENGINE_API_KEY', 'NOT_FOUND')}")
except ImportError:
    print("1. python-dotenv 未安装，跳过")

# 方法2: 手动解析 .env 文件
print("\n2. 手动解析 .env 文件:")
env_path = Path(".env")
if env_path.exists():
    with open(env_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if 'VOLCENGINE' in line.upper() and not line.strip().startswith('#'):
                print(f"   第 {line_num} 行: {repr(line)}")
                # 解析这一行
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    print(f"   解析结果: key='{key}', value='{value}'")
                    print(f"   value 长度: {len(value)} 字符")
                    # 检查是否有隐藏字符
                    print(f"   value 字节: {value.encode('utf-8')}")
else:
    print("   .env 文件不存在")

# 方法3: 使用 pydantic-settings（模拟后端）
print("\n3. 使用 pydantic-settings (模拟后端):")
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    from pydantic import Field
    from typing import Optional
    
    class TestSettings(BaseSettings):
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore",
        )
        
        metaso_api_key: Optional[str] = Field(default=None, alias="METASO_API_KEY")
        baidu_api_key: Optional[str] = Field(default=None, alias="BAIDU_API_KEY")
        volcengine_api_key: Optional[str] = Field(default=None, alias="VOLCENGINE_API_KEY")
    
    test_settings = TestSettings()
    print(f"   metaso_api_key: {'已配置' if test_settings.metaso_api_key else '未配置'}")
    print(f"   baidu_api_key: {'已配置' if test_settings.baidu_api_key else '未配置'}")
    print(f"   volcengine_api_key: {'已配置' if test_settings.volcengine_api_key else '未配置'}")
    
    if test_settings.volcengine_api_key:
        print(f"   volcengine_api_key 值: {test_settings.volcengine_api_key}")
    else:
        print(f"   ✗ volcengine_api_key 为 None 或空字符串")
        
except Exception as e:
    print(f"   ✗ 加载失败: {e}")
    import traceback
    traceback.print_exc()
