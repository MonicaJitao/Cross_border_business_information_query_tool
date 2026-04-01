#!/bin/bash
# 测试运行脚本 - 自动使用正确的 Python 环境

# 项目根目录
PROJECT_ROOT="C:\Users\Monica\Desktop\cross_border_tool"

# cb_tool 环境的 Python 路径
PYTHON_PATH="/d/Space/Anaconda3_Space/envs/cb_tool/python.exe"

# 切换到项目目录
cd "$PROJECT_ROOT"

# 检查 Python 环境是否存在
if [ ! -f "$PYTHON_PATH" ]; then
    echo "❌ 错误: 找不到 cb_tool 环境的 Python"
    echo "路径: $PYTHON_PATH"
    exit 1
fi

echo "✅ 使用 Python: $PYTHON_PATH"
echo "📂 项目目录: $PROJECT_ROOT"
echo ""

# 运行测试
if [ -z "$1" ]; then
    # 没有参数，运行所有测试
    echo "🧪 运行所有测试..."
    "$PYTHON_PATH" -m pytest tests/ -v
else
    # 有参数，运行指定测试
    echo "🧪 运行测试: $1"
    "$PYTHON_PATH" -m pytest "$1" -v
fi
