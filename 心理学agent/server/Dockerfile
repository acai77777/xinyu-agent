FROM python:3.12-slim

WORKDIR /app

# 系统依赖（ffmpeg + C++编译器 for chromadb）
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt

# 预下载 ChromaDB embedding 模型（避免运行时下载 79MB 卡住）
RUN python -c "\
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2; \
ef = ONNXMiniLM_L6_V2(); \
print('Embedding model ready')"

# 应用代码
COPY . .

# 数据目录（挂载卷）
RUN mkdir -p /app/data/memory /app/data/uploads

EXPOSE 8000

# uvicorn 启动
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
