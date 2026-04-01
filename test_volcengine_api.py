#!/usr/bin/env python3
"""测试火山引擎 API 调用"""
import asyncio
import httpx
from backend.app.core.config import settings

async def test_volcengine_api():
    api_key = settings.volcengine_api_key
    
    print("=== 火山引擎 API 测试 ===")
    print(f"API Key (前20字符): {api_key[:20]}..." if api_key else "API Key: 未配置")
    print(f"API Key 完整长度: {len(api_key)}" if api_key else "")
    print(f"API Key 格式检查: {api_key}" if api_key else "")
    
    if not api_key:
        print("✗ 错误: 未配置火山引擎 API Key")
        return
    
    url = "https://open.feedcoopapi.com/search_api/web_search"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "Query": "北京天气",
        "SearchType": "web",
        "Count": 3,
        "Filter": {"NeedUrl": True},
        "NeedSummary": True,
    }
    
    print(f"\n请求 URL: {url}")
    print(f"请求头: {headers}")
    print(f"请求体: {payload}")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            print(f"\n状态码: {resp.status_code}")
            print(f"响应头: {dict(resp.headers)}")
            
            try:
                data = resp.json()
                print(f"\n响应体 (前500字符):")
                import json
                response_text = json.dumps(data, ensure_ascii=False, indent=2)
                print(response_text[:500])
                
                # 检查错误
                if isinstance(data, dict):
                    metadata = data.get("ResponseMetadata", {})
                    error = metadata.get("Error")
                    if error:
                        print(f"\n✗ API 返回错误:")
                        print(f"  错误码: {error.get('CodeN')} / {error.get('Code')}")
                        print(f"  错误信息: {error.get('Message')}")
                    else:
                        result = data.get("Result", {})
                        web_results = result.get("WebResults", [])
                        print(f"\n✓ 搜索成功，返回 {len(web_results)} 条结果")
                        
            except Exception as e:
                print(f"✗ 响应解析失败: {e}")
                print(f"原始响应: {resp.text[:500]}")
                
    except httpx.TimeoutException:
        print("✗ 请求超时")
    except Exception as e:
        print(f"✗ 请求异常: {e}")

if __name__ == "__main__":
    asyncio.run(test_volcengine_api())
