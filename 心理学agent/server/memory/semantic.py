"""
基于ChromaDB的语义记忆
存储用户的关键信息，支持跨会话检索
"""
import math
import uuid
from datetime import datetime

import chromadb

from config import settings


class SemanticMemory:
    def __init__(self, db_path: str | None = None):
        """
        根据环境选择 ChromaDB 连接方式：
        - 开发环境：PersistentClient（嵌入式，零配置）
        - Docker 部署：HttpClient（连接独立容器）
        """
        import os

        if db_path is None:
            db_path = settings.chroma_persist_dir

        chromadb_host = os.getenv("CHROMADB_HOST")
        if chromadb_host:
            self.client = chromadb.HttpClient(
                host=chromadb_host,
                port=int(os.getenv("CHROMADB_PORT", "8001")),
            )
        else:
            self.client = chromadb.PersistentClient(path=db_path)

        self.collection = self.client.get_or_create_collection(
            name="user_memories",
            metadata={"hnsw:space": "cosine"},
        )

    def store(self, user_id: str, text: str, memory_type: str):
        """
        存储记忆片段
        memory_type: emotion_pattern | strength | preference | insight | milestone
        """
        self.collection.add(
            documents=[text],
            ids=[str(uuid.uuid4())],
            metadatas=[{
                "user_id": user_id,
                "type": memory_type,
                "timestamp": datetime.now().isoformat(),
            }],
        )

    def retrieve(self, user_id: str, query: str, top_k: int = 5) -> list[str]:
        """语义检索——找到与查询最相关的记忆"""
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where={"user_id": user_id},
        )
        return results["documents"][0] if results["documents"] else []

    def get_emotion_trend(self, user_id: str) -> list[dict]:
        """获取用户情绪变化趋势"""
        return self.collection.get(
            where={"$and": [
                {"user_id": user_id},
                {"type": "emotion_pattern"},
            ]},
        )

    # === 记忆管理功能（用户的"被遗忘权"）===

    def delete_memory(self, memory_id: str):
        """用户主动删除特定记忆"""
        self.collection.delete(ids=[memory_id])

    def delete_all_user_data(self, user_id: str):
        """彻底删除用户所有数据——账号注销时调用"""
        all_memories = self.collection.get(where={"user_id": user_id})
        if all_memories["ids"]:
            self.collection.delete(ids=all_memories["ids"])

    def list_user_memories(self, user_id: str) -> list[dict]:
        """列出用户所有记忆条目——供用户查看和选择删除"""
        results = self.collection.get(where={"user_id": user_id})
        memories = []
        for i, doc in enumerate(results["documents"]):
            memories.append({
                "id": results["ids"][i],
                "content": doc,
                "type": results["metadatas"][i].get("type", ""),
                "timestamp": results["metadatas"][i].get("timestamp", ""),
            })
        return memories

    def retrieve_with_decay(
        self, user_id: str, query: str, top_k: int = 5, decay_days: int = 90
    ) -> list[dict]:
        """
        带时间衰减的语义检索

        策略：
        - 语义相似度 × 时间衰减因子 = 最终排序分数
        - 衰减公式：decay = exp(-age_days / decay_days)
        - decay_days=90 意味着3个月前的记忆权重降为约37%
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k * 3,  # 多取一些，衰减后再筛
            where={"user_id": user_id},
        )
        if not results["documents"] or not results["documents"][0]:
            return []

        now = datetime.now()
        scored = []
        for i, doc in enumerate(results["documents"][0]):
            ts = results["metadatas"][0][i].get("timestamp", "")
            distance = results["distances"][0][i] if results["distances"] else 1.0
            similarity = 1 - distance  # cosine distance → similarity

            try:
                mem_time = datetime.fromisoformat(ts)
                age_days = (now - mem_time).days
                decay = math.exp(-age_days / decay_days)
            except (ValueError, TypeError):
                age_days = None
                decay = 0.5  # 无时间戳的记忆给中等权重

            final_score = similarity * decay
            scored.append({
                "content": doc,
                "similarity": similarity,
                "age_days": age_days,
                "decay": decay,
                "final_score": final_score,
                "id": results["ids"][0][i],
            })

        scored.sort(key=lambda x: x["final_score"], reverse=True)
        return scored[:top_k]
