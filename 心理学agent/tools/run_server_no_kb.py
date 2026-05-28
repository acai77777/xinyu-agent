"""
临时启动脚本——禁用 ChromaDB（知识库 + 语义记忆），仅用于 e2e 测试。

为什么：本地 chroma ONNX 嵌入模型从 amazonaws.com 下载 ~20kbps，
要 1-2 小时。e2e_test_cross_session.py 验证 SQLite 部分
（narrative_arcs + user_profiles），不需要 chroma。

不修改产品源码，仅 monkey-patch:
1. knowledge.knowledge_base.search_books_semantic → 返回 []
2. memory.semantic.SemanticMemory → no-op 假类
"""
import os
import sys
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent / "server"
sys.path.insert(0, str(SERVER_DIR))
# 切 cwd 到 server/，让 pydantic-settings 找到 .env，
# 同时 ./data/chroma、知识库相对路径都正确解析。
os.chdir(SERVER_DIR)

# --- 1. 知识库 stub ---
import knowledge.knowledge_base as kb


def _kb_stub(query: str, max_results: int = 5) -> list[dict]:
    return []


kb.search_books_semantic = _kb_stub
print("[stub] knowledge_base.search_books_semantic disabled", flush=True)


# --- 2. SemanticMemory stub ---
class _FakeSemanticMemory:
    def __init__(self, *args, **kwargs):
        pass

    def store(self, *args, **kwargs):
        return "stub-id"

    def retrieve_with_decay(self, *args, **kwargs):
        return []

    def retrieve(self, *args, **kwargs):
        return []

    def list_user_memories(self, user_id):
        return []

    def delete_memory(self, memory_id):
        return None

    def delete_all_user_data(self, user_id):
        return None

    def get_emotion_trend(self, user_id):
        return {"ids": [], "documents": [], "metadatas": []}


import memory.semantic as semantic_mod

semantic_mod.SemanticMemory = _FakeSemanticMemory
print("[stub] memory.semantic.SemanticMemory replaced with no-op", flush=True)


import uvicorn

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
