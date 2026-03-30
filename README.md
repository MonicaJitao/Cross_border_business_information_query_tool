# 跨境业务企业信息查询工具

上传含企业名单的 Excel → 调用秘塔搜索 + LLM 自动抽取 9 个跨境标签 + 4 个摘要维度 → 下载结果 Excel。

## 快速启动

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，填入你的 Key：

```bash
cp .env.example .env
```

必填项：

| 变量 | 说明 |
|------|------|
| `METASO_API_KEY` | 秘塔 AI 搜索 API Key（[获取地址](https://metaso.cn/search-api/playground)） |
| `DEEPSEEK_API_KEY` 或 `CLAUDE_PROXY_API_KEY` | 至少填一个 LLM Key |
| `CLAUDE_PROXY_BASE_URL` | 若用 Claude 中转站，填入中转站地址 |

### 3. 启动后端

在项目根目录运行：

```bash
uvicorn backend.app.main:app --reload --port 8000
```

### 4. 打开前端

浏览器访问：[http://localhost:8000](http://localhost:8000)

---

## 输入 Excel 格式

- 第一列：企业名称（任意列名均可）
- 其余列忽略
- 支持 `.xlsx` / `.xls`

## 输出 Excel 列

| 列名 | 说明 |
|------|------|
| 企业名称 | 输入原文 |
| 进出口业务 | 有 / 无 / 不确定 |
| 境外主体 | 有 / 无 / 不确定（如有则含简述） |
| 客户行业 | 多个行业以逗号分隔 |
| 主要产品 | 主营商品 |
| 贸易方式 | 一般贸易 / 加工贸易 / 跨境电商等 |
| 结算货币 | USD / HKD / EUR 等 |
| 物流模式 | 海运 / 空运 / 陆运 / 多式联运 |
| 合规风险信号 | 如有则填写，否则为空 |
| 数据置信度 | 高 / 中 / 低 |
| 香港主体情况 | 摘要 |
| 进出口业务概述 | 摘要 |
| 行业概述 | 摘要 |
| 营收规模 | 摘要（有公开数据时） |
| 证据条数 | 搜索命中数 |
| 来源URL | 前 5 个来源 |
| 错误信息 | 若处理失败则显示原因 |

---

## 并发与吞吐估算

| 搜索并发 | LLM 并发 | 估算吞吐 |
|---------|---------|---------|
| 5 | 3 | ~300 企业/小时 |
| 10 | 5 | ~700 企业/小时 |
| 15 | 8 | ~1100 企业/小时 |

> 实际吞吐受网络延迟与 Provider 限速影响，以 SSE 实时数据为准。

---

## 架构说明

```
frontend/
  index.html   单页应用入口
  styles.css   CSS 变量设计系统
  app.js       前端状态机

backend/app/
  main.py                          FastAPI 入口
  api/jobs.py                      REST + SSE 接口
  core/config.py                   环境变量管理
  services/
    search/base.py                 SearchProvider 抽象
    search/metaso.py               秘塔实现（自适应限流）
    llm/base.py                    LLMProvider 抽象
    llm/openai_compat.py           OpenAI 兼容调用
    llm/factory.py                 Provider 工厂
    extract/schema.py              Pydantic 结构定义
    extract/prompt.py              提示词模板
    extract/parse.py               三层 JSON fallback
    extract/extractor.py           抽取主逻辑
    pipeline/runner.py             异步并发 + 退避
    pipeline/keywords.py           关键词逐步加码策略
    storage/job_store.py           内存 Job 存储
```
