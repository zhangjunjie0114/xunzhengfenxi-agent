#!/bin/bash

# ============================================================
# 循证分析智能体 - 一键启动脚本
# 双击此文件即可运行（Mac）
# ============================================================

# 获取脚本所在目录
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo ""
echo "========================================"
echo "  🔬 循证分析智能体 (Evidence Analysis Agent)"
echo "========================================"
echo ""
echo "📂 项目路径: $DIR"
echo ""

# 检查 Python 是否安装
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未检测到 Python 3"
    echo "   请先安装 Python: https://www.python.org/downloads/"
    echo ""
    read -p "按 Enter 键退出..."
    exit 1
fi

echo "✅ Python 版本: $(python3 --version)"

# 检查/安装依赖
echo ""
echo "📦 检查依赖..."
python3 -c "
import sys
pkgs = ['streamlit', 'anthropic', 'PyMuPDF', 'plotly', 'pandas', 'matplotlib', 'openai', 'requests']
missing = []
for p in pkgs:
    try:
        __import__(p.replace('-', '_'))
    except ImportError:
        missing.append(p)
if missing:
    print(f'缺少 {len(missing)} 个包，正在安装...')
    import subprocess
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt', '-q'])
    print('✅ 依赖安装完成')
else:
    print('✅ 所有依赖已就绪')
"

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ 依赖安装失败"
    echo "   请手动运行: pip3 install -r requirements.txt"
    read -p "按 Enter 键退出..."
    exit 1
fi

# 检查 API Key 配置
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  提示: 未检测到 .env 文件"
    echo "   启动后请在左侧面板中输入 API Key"
    echo ""
fi

# 启动应用
echo ""
echo "🌐 正在启动应用..."
echo "   浏览器打开后即可使用"
echo ""
echo "   如果浏览器没有自动打开，请访问:"
echo "   http://localhost:8501"
echo ""
echo "   按 Ctrl+C 停止应用"
echo "========================================"
echo ""

streamlit run app.py --server.port 8501

# 如果退出
echo ""
echo "应用已停止"
read -p "按 Enter 键关闭..."
