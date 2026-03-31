<a id="readme-top"></a>

<!-- 项目 SHIELDS -->
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]

<!-- 项目 LOGO -->
<br />
<div align="center">
  <h1 align="center">🌐 跨境业务企业信息查询工具</h1>

  <p align="center">
    基于 AI 搜索和大语言模型的企业跨境业务信息自动化抽取系统
    <br />
    <a href="#使用说明"><strong>查看文档 »</strong></a>
    <br />
    <br />
    <a href="#快速开始">快速开始</a>
    ·
    <a href="https://github.com/your_username/cross_border_tool/issues">报告 Bug</a>
    ·
    <a href="https://github.com/your_username/cross_border_tool/issues">功能建议</a>
  </p>
</div>

<!-- 目录 -->
<details>
  <summary>目录</summary>
  <ol>
    <li>
      <a href="#关于项目">关于项目</a>
      <ul>
        <li><a href="#核心功能">核心功能</a></li>
        <li><a href="#技术栈">技术栈</a></li>
      </ul>
    </li>
    <li>
      <a href="#快速开始">快速开始</a>
      <ul>
        <li><a href="#环境要求">环境要求</a></li>
        <li><a href="#安装步骤">安装步骤</a></li>
      </ul>
    </li>
    <li><a href="#使用说明">使用说明</a></li>
    <li><a href="#架构设计">架构设计</a></li>
    <li><a href="#路线图">路线图</a></li>
    <li><a href="#贡献指南">贡献指南</a></li>
    <li><a href="#许可证">许可证</a></li>
    <li><a href="#联系方式">联系方式</a></li>
  </ol>
</details>

<!-- 关于项目 -->
## 关于项目

跨境业务企业信息查询工具是一个自动化的企业信息抽取系统，通过上传包含企业名单的 Excel 文件，系统会自动调用 AI 搜索引擎和大语言模型，批量提取企业的跨境业务相关信息，最终生成结构化的 Excel 报告。

### 核心功能

* 📊 **批量处理** - 支持一次性处理数百家企业，自动化程度高
* 🔍 **多源搜索** - 集成秘塔 AI 搜索、百度千帆等多个搜索源
* 🤖 **智能抽取** - 使用 DeepSeek、Claude 等大语言模型进行结构化信息抽取
* 📈 **实时进度** - SSE 实时推送处理进度和详细日志
* 💾 **断点续传** - 支持从历史结果继续处理，避免重复查询
* 🎯 **动态字段** - 18 个内置字段 + 支持自定义字段扩展
* ⚡ **并发控制** - 可调节搜索和 LLM 并发数，优化吞吐量

### 抽取字段

**总结维度（9 个）**
- 是否有香港主体、是否有非香港海外主体、海外主体所在国家
- 是否有进出口业务、进出口业务涉及国家、进出口主要模式
- 年进出口金额、企业所属行业、企业年营收规模

**标签维度（9 个）**
- 进出口业务、境外主体、出海规划、外汇业务、结售汇业务
- 客户行业、经营规模、进出口地区、出海地区

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

### 技术栈

**后端**

* [![FastAPI][FastAPI-badge]][FastAPI-url]
* [![Python][Python-badge]][Python-url]
* [![Pandas][Pandas-badge]][Pandas-url]
* [![Pydantic][Pydantic-badge]][Pydantic-url]

**前端**

* [![JavaScript][JavaScript-badge]][JavaScript-url]
* [![HTML5][HTML5-badge]][HTML5-url]
* [![CSS3][CSS3-badge]][CSS3-url]

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

<!-- 快速开始 -->
## 快速开始

### 环境要求

* Python 3.9+
* pip 包管理器

### 安装步骤

1. **获取 API Key**

   至少需要以下 API Key 之一：
   - 秘塔 AI 搜索 API Key：[https://metaso.cn/search-api/playground](https://metaso.cn/search-api/playground)
   - DeepSeek API Key：[https://platform.deepseek.com](https://platform.deepseek.com)
   - Claude API Key（可选，需中转站）

2. **克隆仓库**
   ```bash
   git clone https://github.com/your_username/cross_border_tool.git
   cd cross_border_tool
   ```

3. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

4. **配置环境变量**

   复制 `.env.example` 为 `.env`，填入你的 API Key：
   ```bash
   cp .env.example .env
   ```

   编辑 `.env` 文件：
   ```env
   # 搜索源（必填）
   METASO_API_KEY=your_metaso_key_here

   # LLM（至少填一个）
   DEEPSEEK_API_KEY=sk-xxx
   CLAUDE_PROXY_BASE_URL=https://your-proxy.example.com/v1
   CLAUDE_PROXY_API_KEY=sk-xxx
   ```

5. **启动服务**
   ```bash
   uvicorn backend.app.main:app --reload --port 8000
   ```

6. **访问应用**

   浏览器打开：[http://localhost:8000](http://localhost:8000)

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

<!-- 使用说明 -->
## 使用说明

### 1. 准备 Excel 文件

准备包含企业名单的 Excel 文件（.xlsx 或 .xls）：
- 第一列应为企业名称（列名任意）
- 其余列会被忽略
- 支持续传：可上传之前下载的结果文件，已处理的企业会自动跳过

### 2. 配置参数

**搜索策略**
- 选择搜索源（秘塔 AI 搜索、百度千帆，可多选）
- 设置每源检索条数（5-50 条）

**字段配置**
- 勾选需要抽取的字段（默认全选）
- 支持添加自定义字段

**大模型选择**
- DeepSeek 官方（推荐，性价比高）
- Claude 中转站（需自建中转服务）

**并发控制**
- 搜索并发：1-20（默认 5）
- LLM 并发：1-10（默认 3）
- 估算吞吐：300-1100 企业/小时

### 3. 上传并开始

- 点击或拖拽上传 Excel 文件
- 点击"开始批量查询"按钮
- 实时查看处理进度和日志

### 4. 下载结果

- 处理完成后点击"下载结果 Excel"
- 结果包含所有选定字段 + 证据条数 + 来源 URL

### 输出示例

| 企业名称 | 是否有香港主体 | 是否有进出口业务 | 进出口业务涉及国家 | 企业所属行业 | 证据条数 | 来源URL |
|---------|--------------|----------------|------------------|------------|---------|---------|
| XX科技有限公司 | 有 | 有 | 美国、日本、德国 | 精密仪器制造 | 12 | https://... |

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

<!-- 架构设计 -->
## 架构设计

### 系统架构

```
┌─────────────┐
│   前端 UI    │  (HTML + CSS + Vanilla JS)
└──────┬──────┘
       │ REST + SSE
┌──────▼──────────────────────────────┐
│         FastAPI 后端                 │
├─────────────────────────────────────┤
│  ┌─────────┐  ┌──────────┐         │
│  │ 搜索层   │  │  LLM 层   │         │
│  │ Metaso  │  │ DeepSeek │         │
│  │ Baidu   │  │ Claude   │         │
│  └─────────┘  └──────────┘         │
│         │            │              │
│  ┌──────▼────────────▼───────┐     │
│  │   Pipeline 编排层          │     │
│  │ (异步并发 + 进度推送)       │     │
│  └───────────────────────────┘     │
└─────────────────────────────────────┘
```

### 核心模块

**搜索层** (`backend/app/services/search/`)
- 抽象接口 `SearchProvider`
- 多搜索源并行调用 + URL 去重
- 自适应限流 + 指数退避

**LLM 层** (`backend/app/services/llm/`)
- 抽象接口 `LLMProvider`
- 工厂模式支持多 LLM 切换
- OpenAI 兼容协议

**抽取层** (`backend/app/services/extract/`)
- 动态 Prompt 构建
- 三层 JSON 解析容错
- 字段目录管理

**Pipeline 层** (`backend/app/services/pipeline/`)
- 异步并发控制（Semaphore）
- 关键词逐步加码策略
- SSE 实时进度推送

### 数据流

```
Excel 上传 → 解析企业名单 → 并发处理
                              ↓
                    ┌─────────┴─────────┐
                    │  单企业处理流程    │
                    ├──────────────────┤
                    │ 1. 关键词搜索     │
                    │ 2. 多源聚合去重   │
                    │ 3. LLM 结构化抽取 │
                    │ 4. 结果验证       │
                    └─────────┬─────────┘
                              ↓
                    汇总结果 → 生成 Excel
```

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

<!-- 路线图 -->
## 路线图

- [x] 基础功能实现
  - [x] 多搜索源支持
  - [x] 多 LLM 支持
  - [x] 动态字段系统
  - [x] 续传机制
- [ ] 功能增强
  - [ ] SQLite 持久化存储
  - [ ] 用户认证系统
  - [ ] 批量任务管理
  - [ ] 导出格式扩展（CSV、JSON）
- [ ] 性能优化
  - [ ] 搜索结果缓存
  - [ ] LLM 响应缓存
  - [ ] 分布式任务队列
- [ ] 可观测性
  - [ ] Prometheus 指标
  - [ ] 日志聚合
  - [ ] 成本统计

查看 [open issues](https://github.com/your_username/cross_border_tool/issues) 了解完整的功能规划和已知问题。

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

<!-- 贡献指南 -->
## 贡献指南

欢迎贡献！如果你有好的建议，请 fork 本仓库并创建 pull request。你也可以直接提交 issue 并打上 "enhancement" 标签。

1. Fork 本项目
2. 创建你的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交你的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启一个 Pull Request

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

<!-- 许可证 -->
## 许可证

本项目采用 MIT 许可证。详见 `LICENSE` 文件。

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

<!-- 联系方式 -->
## 联系方式

项目链接: [https://github.com/your_username/cross_border_tool](https://github.com/your_username/cross_border_tool)

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

<!-- 致谢 -->
## 致谢

* [FastAPI](https://fastapi.tiangolo.com/)
* [秘塔 AI 搜索](https://metaso.cn/)
* [DeepSeek](https://www.deepseek.com/)
* [Best-README-Template](https://github.com/othneildrew/Best-README-Template)

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
[contributors-shield]: https://img.shields.io/github/contributors/your_username/cross_border_tool.svg?style=for-the-badge
[contributors-url]: https://github.com/your_username/cross_border_tool/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/your_username/cross_border_tool.svg?style=for-the-badge
[forks-url]: https://github.com/your_username/cross_border_tool/network/members
[stars-shield]: https://img.shields.io/github/stars/your_username/cross_border_tool.svg?style=for-the-badge
[stars-url]: https://github.com/your_username/cross_border_tool/stargazers
[issues-shield]: https://img.shields.io/github/issues/your_username/cross_border_tool.svg?style=for-the-badge
[issues-url]: https://github.com/your_username/cross_border_tool/issues
[license-shield]: https://img.shields.io/github/license/your_username/cross_border_tool.svg?style=for-the-badge
[license-url]: https://github.com/your_username/cross_border_tool/blob/master/LICENSE

<!-- 技术栈 Badges -->
[FastAPI-badge]: https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white
[FastAPI-url]: https://fastapi.tiangolo.com/
[Python-badge]: https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white
[Python-url]: https://www.python.org/
[Pandas-badge]: https://img.shields.io/badge/Pandas-150458?style=for-the-badge&logo=pandas&logoColor=white
[Pandas-url]: https://pandas.pydata.org/
[Pydantic-badge]: https://img.shields.io/badge/Pydantic-E92063?style=for-the-badge&logo=pydantic&logoColor=white
[Pydantic-url]: https://docs.pydantic.dev/
[JavaScript-badge]: https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black
[JavaScript-url]: https://developer.mozilla.org/en-US/docs/Web/JavaScript
[HTML5-badge]: https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white
[HTML5-url]: https://developer.mozilla.org/en-US/docs/Web/HTML
[CSS3-badge]: https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white
[CSS3-url]: https://developer.mozilla.org/en-US/docs/Web/CSS
