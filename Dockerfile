# 使用 Python 3.11 镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装必要的系统工具
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# 拷贝依赖并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝你的所有代码和 JSON 凭据 (确保 JSON 文件在同一个文件夹)
COPY . .

# 关键：Streamlit 需要设置固定端口和开启无头模式
# Cloud Run 会通过 $PORT 注入端口，我们将 Streamlit 绑定到该端口
EXPOSE 8080

CMD ["sh", "-c", "streamlit run main.py --server.port=${PORT} --server.address=0.0.0.0"]
