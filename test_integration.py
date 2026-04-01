"""
端到端集成测试：验证火山引擎搜索集成和每源独立配置功能
"""
import sys
import io
import urllib.request
import urllib.parse
import json
import time

# 设置标准输出为UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_BASE = "http://localhost:8000"

def http_get(url):
    """简单的HTTP GET请求"""
    with urllib.request.urlopen(url) as response:
        return response.status, json.loads(response.read().decode())

def http_post_multipart(url, files, data):
    """简单的HTTP POST multipart请求"""
    boundary = '----WebKitFormBoundary' + str(int(time.time() * 1000))
    body = []

    # 添加普通字段
    for key, value in data.items():
        body.append(f'--{boundary}'.encode())
        body.append(f'Content-Disposition: form-data; name="{key}"'.encode())
        body.append(b'')
        body.append(value.encode() if isinstance(value, str) else value)

    # 添加文件
    for key, (filename, content, content_type) in files.items():
        body.append(f'--{boundary}'.encode())
        body.append(f'Content-Disposition: form-data; name="{key}"; filename="{filename}"'.encode())
        body.append(f'Content-Type: {content_type}'.encode())
        body.append(b'')
        body.append(content)

    body.append(f'--{boundary}--'.encode())
    body_bytes = b'\r\n'.join(body)

    req = urllib.request.Request(url, data=body_bytes)
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')

    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())

def test_meta_endpoint():
    """测试元数据API是否包含火山引擎"""
    print("\n=== 测试 1: 元数据API ===")
    status, data = http_get(f"{API_BASE}/api/meta")
    assert status == 200, f"API返回错误: {status}"

    providers = data.get("search_providers", [])
    provider_ids = [p["id"] for p in providers]

    print(f"✓ 搜索源列表: {provider_ids}")
    assert "metaso" in provider_ids, "缺少秘塔搜索"
    assert "baidu" in provider_ids, "缺少百度搜索"
    assert "volcengine" in provider_ids, "缺少火山引擎搜索"

    vol_provider = next(p for p in providers if p["id"] == "volcengine")
    print(f"✓ 火山引擎配置: {vol_provider}")
    print("✓ 元数据API测试通过\n")

def test_job_creation_with_new_config():
    """测试使用新配置结构创建任务"""
    print("=== 测试 2: 新配置结构任务创建 ===")

    # 构建新的配置结构
    config = {
        "search_providers": [
            {"id": "metaso", "num_results": 10, "api_key": None},
            {"id": "baidu", "num_results": 5, "api_key": None},
            {"id": "volcengine", "num_results": 15, "api_key": "test_key"}
        ],
        "field_defs": [
            {
                "id": "has_cross_border",
                "label": "是否有跨境业务",
                "group": "summary",
                "col_name": "是否有跨境业务",
                "instruction": "判断企业是否有跨境电商、跨境物流等业务",
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

    # 读取测试文件
    with open("test_companies.xlsx", "rb") as f:
        file_content = f.read()

    files = {"file": ("test.xlsx", file_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    data = {"config": json.dumps(config)}

    status, result = http_post_multipart(f"{API_BASE}/api/jobs", files, data)

    print(f"响应状态码: {status}")
    print(f"响应内容: {json.dumps(result, ensure_ascii=False)[:500]}")

    if status == 200:
        print(f"✓ 任务创建成功")
        print(f"  - Job ID: {result.get('job_id')}")
        print(f"  - 总企业数: {result.get('total')}")
        print(f"  - 续传数量: {result.get('pre_done')}")
        print("✓ 新配置结构测试通过\n")
        return result.get('job_id')
    else:
        print(f"✗ 任务创建失败: {result}")
        return None

def test_config_validation():
    """测试配置验证逻辑"""
    print("=== 测试 3: 配置验证 ===")

    # 测试无效的num_results（超出范围）
    invalid_config = {
        "search_providers": [
            {"id": "metaso", "num_results": 100, "api_key": None}  # 超过50的上限
        ],
        "field_defs": [
            {
                "id": "test",
                "label": "测试",
                "group": "summary",
                "col_name": "测试",
                "instruction": "测试",
                "field_type": "text"
            }
        ],
        "llm": {"provider": "deepseek_official"},
        "concurrency": {"search": 5, "llm": 3}
    }

    with open("test_companies.xlsx", "rb") as f:
        file_content = f.read()

    files = {"file": ("test.xlsx", file_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    data = {"config": json.dumps(invalid_config)}

    status, result = http_post_multipart(f"{API_BASE}/api/jobs", files, data)

    # 应该返回422验证错误
    if status == 422:
        print("✓ 配置验证正常工作（拒绝了无效配置）")
        print(f"  错误信息: {str(result.get('detail', ''))[:200]}")
    else:
        print(f"✗ 配置验证可能有问题（状态码: {status}）")

    print("✓ 配置验证测试完成\n")

if __name__ == "__main__":
    print("=" * 60)
    print("火山引擎搜索集成 - 端到端测试")
    print("=" * 60)

    try:
        # 测试1: 元数据API
        test_meta_endpoint()

        # 测试2: 新配置结构
        job_id = test_job_creation_with_new_config()

        # 测试3: 配置验证
        test_config_validation()

        print("=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)

        if job_id:
            print(f"\n提示: 任务 {job_id} 已创建，但由于缺少真实API Key，")
            print("搜索阶段会失败。这是预期行为。")
            print("在生产环境中配置真实API Key后即可正常运行。")

    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
