@echo off
echo 🔬 循证分析智能体 (Evidence Analysis Agent)
echo 正在启动...
cd /d "%~dp0"

python -c "import streamlit" 2>nul
if %errorlevel% neq 0 (
    echo ⚠️  正在安装依赖...
    pip install -r requirements.txt
)

if not exist ".env" (
    echo ⚠️  未检测到 .env 文件，请在启动后在配置面板中输入 API Key
)

echo 🌐 浏览器打开后即可使用
streamlit run app.py --server.port 8501 --server.headless true
