## Identity & Addressing

* Call me Monica every time you answer.
* Always respond in Chinese-simplified.



## Terminal & System Operation Rule

When suggesting terminal commands or system operations:

1. Explain the "Why": Briefly explain what the command does and why it is necessary in this context.
2. Explain the "How": Provide the exact command in a code block.
3. Constraint: Do NOT execute the command automatically. Wait for Monica to confirm the execution.



## Behavior Principles

* Be ashamed of guessing APIs in the dark; be proud of reading the docs carefully.
* Be ashamed of vague execution; be proud of seeking clarification and confirmation.
* Be ashamed of armchair business theorizing; be proud of validating with real people.
* Be ashamed of inventing new APIs for no reason; be proud of reusing what already exists.
* Be ashamed of skipping validation; be proud of proactive testing.
* Be ashamed of breaking the architecture; be proud of following standards and conventions.
* Be ashamed of pretending to understand; be proud of honest "I don't know."
* Be ashamed of blind edits; be proud of careful refactoring.

## Bug Fixing
There's a file modification bug in Claude Code. The workaround is: always use complete absolute Windows paths with drive letters and backslashes for ALL file operations. Apply this rule going forward, not just for this file.



---

# 项目配置指南

## 测试环境

**重要：本项目必须在 cb_tool conda 环境中运行测试**

### Python 解释器路径
```
/d/Space/Anaconda3_Space/envs/cb_tool/python.exe
```

### 运行测试的正确方式

**✅ 正确：**
```bash
cd "C:\Users\Monica\Desktop\cross_border_tool"
/d/Space/Anaconda3_Space/envs/cb_tool/python.exe -m pytest tests/ -v
```

**❌ 错误（会缺少依赖）：**
```bash
pytest tests/ -v  # 使用默认 Python，缺少 pydantic 等依赖
```

### 为什么不用 conda activate？

在 Git Bash 环境中，`conda activate cb_tool` 可能不工作。直接使用完整的 Python 路径更可靠。

## Git 配置

**个人 GitHub 账户（必须使用）：**
```bash
git config user.name "MonicaJitao"
git config user.email "monica.jitao@gmail.com"
```

**⚠️ 绝对不能使用公司账户 (@tcl.com)！**

## 项目结构

- **后端**: `backend/app/services/`
  - `extract/`: 字段提取逻辑（schema, fields, prompt, parse）
  - `pipeline/`: 搜索关键词生成
  - `storage/`: Excel 导出
- **前端**: `frontend/`
  - `app.js`: 主要逻辑
  - `index.html`: 页面结构
  - `styles.css`: 样式
- **测试**: `tests/`
  - 27 个测试，覆盖所有核心功能

## 当前字段结构

- **10 个核心字段**（总结维度）
- **每个字段配备备注列**（summary_notes）
- **标签维度已删除**（TAGS_FIELDS = []）

## 运行开发服务器

```bash
uvicorn backend.app.main:app --reload --port 8000
```

访问: http://localhost:8000

## 依赖管理

项目依赖已安装在 cb_tool 环境中，包括：
- pydantic
- pandas
- openpyxl
- pytest
- fastapi
- uvicorn

如需更新依赖，在 cb_tool 环境中操作。
