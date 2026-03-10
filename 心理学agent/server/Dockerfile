FROM python:3.12-slim

WORKDIR /app

# 系统依赖（音频处理需要 ffmpeg）
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码
COPY . .

# 数据目录（挂载卷）
RUN mkdir -p /app/data/memory /app/data/uploads

EXPOSE 8000

# uvicorn 启动
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
