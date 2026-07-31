FROM python:3.12-slim

WORKDIR /app

# 安装 PyMuPDF 需要的系统库
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 创建 sessions 目录（挂载点）
RUN mkdir -p /app/sessions

EXPOSE 8501

# Streamlit 配置：不自动打开浏览器，监听所有网络接口
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--server.enableCORS=false", \
     "--server.enableXsrfProtection=false"]
