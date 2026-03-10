"""
pytest 共用 fixtures
"""
import sys
import os
from pathlib import Path

# 将 server 目录加入 sys.path，使 import 能正常工作
SERVER_DIR = Path(__file__).resolve().parent.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

# 设置最小化环境变量，避免测试时读取真实 .env
os.environ.setdefault("LLM_PROVIDER", "deepseek")
os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("SQLITE_DB_PATH", ":memory:")
