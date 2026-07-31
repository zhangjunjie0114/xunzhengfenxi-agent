#!/bin/bash
echo "🔬 循证分析智能体 (Evidence Analysis Agent)"
echo "正在启动..."
cd "$(dirname "$0")"

# 检查依赖
python3 -c "import streamlit" 2>/dev/null || {
    echo "⚠️  正在安装依赖..."
    pip install -r requirements.txt
}

if [ ! -f ".env" ]; then
    echo "⚠️  未检测到 .env 文件，请在启动后在配置面板中输入 API Key"
fi

echo "🌐 浏览器打开后即可使用"
streamlit run app.py --server.port 8501 --server.headless true
