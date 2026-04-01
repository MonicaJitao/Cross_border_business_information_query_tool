# 火山引擎搜索集成 - 使用指南

## 功能概述

本次更新实现了两个核心功能：
1. **火山引擎联网搜索集成** - 新增第三个搜索源
2. **每源独立配置** - 每个搜索源可以设置不同的检索数量

## 快速开始

### 1. 配置火山引擎 API Key

**方式一：后端预置（推荐生产环境）**
```bash
# 在 .env 文件中添加
VOLCENGINE_API_KEY=your_api_key_here
```

**方式二：前端输入（推荐开发测试）**
- 在前端界面勾选"火山引擎搜索"
- 输入 API Key
- 或勾选"使用后端预置 Key"（如果后端已配置）

### 2. 配置检索数量

每个搜索源现在都有独立的检索数量下拉框：
- **秘塔AI搜索**：5/10/20/30/50 条（默认10条）
- **百度千帆搜索**：5/10/20/30/50 条（默认10条）
- **火山引擎搜索**：5/10/20/30/50 条（默认10条）

**配置建议**：
```
高质量源（秘塔）：20条
成本较高源（百度）：5条
免费额度源（火山）：10条
```

### 3. 启动服务

```bash
# 启动后端
cd c:\Users\Monica\Desktop\cross_border_tool
/d/Space/Anaconda3_Space/envs/cb_tool/python.exe -m uvicorn backend.app.main:app --reload --port 8000

# 访问前端
http://localhost:8000
```

## 技术细节

### 配置结构变更

**旧配置（已废弃）**：
```json
{
  "search_providers": ["metaso", "baidu"],
  "metaso_api_key": "xxx",
  "baidu_api_key": "xxx",
  "search_result_limit": 10
}
```

**新配置（当前版本）**：
```json
{
  "search_providers": [
    {"id": "metaso", "num_results": 20, "api_key": null},
    {"id": "baidu", "num_results": 5, "api_key": null},
    {"id": "volcengine", "num_results": 15, "api_key": "xxx"}
  ]
}
```

### 搜索结果聚合机制

1. **并行搜索**：所有选中的搜索源同时调用
2. **URL去重**：相同URL只保留第一个结果
3. **指纹去重**：无URL时按 `title[:60] + snippet[:60]` 去重
4. **结果合并**：最终证据数 = 各源检索数之和（去重后）

**示例**：
```
秘塔检索20条 + 百度检索5条 + 火山检索15条
→ 去重后可能得到 10-40 条证据（取决于重复率）
```

### 火山引擎 API 特性

- **端点**：`https://open.feedcoopapi.com/search_api/web_search`
- **认证**：`Authorization: Bearer <API_KEY>`
- **速率限制**：默认 5 QPS（最小间隔0.2秒）
- **最大条数**：50条/次
- **响应结构**：双层结构（ResponseMetadata + Result.WebResults）

## 测试验证

运行集成测试：
```bash
cd c:\Users\Monica\Desktop\cross_border_tool
/d/Space/Anaconda3_Space/envs/cb_tool/python.exe test_integration.py
```

**预期输出**：
```
✓ 搜索源列表: ['metaso', 'baidu', 'volcengine']
✓ 火山引擎配置: {'id': 'volcengine', 'name': '火山引擎搜索', 'has_preset_key': False}
✓ 任务创建成功
✓ 配置验证正常工作
✓ 所有测试通过！
```

## 故障排查

### 问题1：火山引擎搜索失败
**症状**：日志显示 "volcengine_auth_error_401"
**解决**：检查 API Key 是否正确，确认是否有访问权限

### 问题2：配置验证失败
**症状**：提交任务时返回 422 错误
**解决**：检查 `num_results` 是否在 1-50 范围内

### 问题3：前端不显示火山引擎选项
**症状**：只看到秘塔和百度
**解决**：
1. 清除浏览器缓存
2. 检查后端 `/api/meta` 是否返回火山引擎配置
3. 确认前端文件已更新

## 性能优化建议

1. **搜索并发**：建议设置为 5（默认值）
2. **LLM并发**：建议设置为 3（默认值）
3. **检索数量**：
   - 小批量任务（<50家）：可以设置较大值（20-30条）
   - 大批量任务（>100家）：建议设置较小值（5-10条）以控制成本

## 向后兼容性

旧的配置结构仍然被接受（通过 `metaso_api_key` 和 `baidu_api_key` 字段），但建议迁移到新的配置结构以获得更好的灵活性。

## 更新日志

**2026-04-01**
- ✅ 新增火山引擎搜索Provider
- ✅ 重构配置结构支持每源独立配置
- ✅ 前端UI添加火山引擎选项和独立检索数量配置
- ✅ 完成端到端集成测试
- ✅ 更新文档和使用指南

## 联系方式

如有问题，请联系 Monica (monica.jitao@gmail.com)
