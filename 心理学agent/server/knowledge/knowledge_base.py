"""
知识库检索模块——从 JSON 数据文件中加载和检索心理学知识
支持按书籍、主题、关键词搜索 + ChromaDB 语义检索
"""
import json
import os
from pathlib import Path

from config import settings

_KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "data" / "knowledge"

# 缓存已加载的知识库
_kb_cache: dict[str, dict] = {}

# 书籍文件映射
_BOOK_FILES = {
    "cbt": "cbt_theory.json",
    "authentic_happiness": "authentic_happiness.json",
    "positive_psychology": "positive_psychology.json",
}


def _load_book(book_key: str) -> dict | None:
    """加载指定书籍的知识数据"""
    if book_key in _kb_cache:
        return _kb_cache[book_key]

    filename = _BOOK_FILES.get(book_key)
    if not filename:
        return None

    filepath = _KNOWLEDGE_DIR / filename
    if not filepath.exists():
        return None

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    _kb_cache[book_key] = data
    return data


def _load_all_books() -> dict[str, dict]:
    """加载所有书籍"""
    result = {}
    for key in _BOOK_FILES:
        data = _load_book(key)
        if data:
            result[key] = data
    return result


def get_topic(book_key: str, topic_key: str) -> dict | None:
    """
    按书籍+主题获取完整知识条目。

    book_key: "cbt" / "authentic_happiness" / "positive_psychology"
    topic_key: 如 "cognitive_model", "perma_model", "self_compassion"
    """
    book = _load_book(book_key)
    if not book:
        return None
    return book.get("topics", {}).get(topic_key)


def get_plain_explanation(topic_key: str) -> str | None:
    """
    获取某主题的通俗解释（跨书籍搜索）。
    返回 plain_explanation 字符串，未找到返回 None。
    """
    books = _load_all_books()
    for book_data in books.values():
        topic = book_data.get("topics", {}).get(topic_key)
        if topic and "plain_explanation" in topic:
            return topic["plain_explanation"]
    return None


def search_knowledge(query: str, max_results: int = 10) -> list[dict]:
    """
    按关键词搜索知识条目。
    在标题、通俗解释、关键原则等字段中匹配。

    返回 [{book, topic_key, title, plain_explanation, relevance_fields}, ...]
    """
    query_lower = query.lower()
    results = []

    books = _load_all_books()
    for book_key, book_data in books.items():
        book_name = book_data.get("book", book_key)

        for topic_key, topic in book_data.get("topics", {}).items():
            matched_fields = []

            # 搜索标题
            title = topic.get("title", "")
            title_en = topic.get("title_en", "")
            if query_lower in title.lower() or query_lower in title_en.lower():
                matched_fields.append("title")

            # 搜索通俗解释
            explanation = topic.get("plain_explanation", "")
            if query_lower in explanation.lower():
                matched_fields.append("plain_explanation")

            # 搜索关键原则
            for principle in topic.get("key_principles", []):
                if query_lower in principle.lower():
                    matched_fields.append("key_principles")
                    break

            # 搜索隐喻
            metaphor = topic.get("metaphor", "")
            if query_lower in metaphor.lower():
                matched_fields.append("metaphor")

            # 搜索练习
            for practice in topic.get("practices", []):
                if isinstance(practice, str) and query_lower in practice.lower():
                    matched_fields.append("practices")
                    break
                elif isinstance(practice, dict):
                    for v in practice.values():
                        if isinstance(v, str) and query_lower in v.lower():
                            matched_fields.append("practices")
                            break

            # 搜索子主题
            for sub_key, sub in topic.get("subtopics", {}).items():
                sub_title = sub.get("title", "")
                sub_explanation = sub.get("explanation", "")
                if query_lower in sub_title.lower() or query_lower in sub_explanation.lower():
                    matched_fields.append(f"subtopics.{sub_key}")

            # 搜索技术子项
            for tech_key, tech in topic.get("items", {}).items():
                tech_title = tech.get("title", "")
                tech_explanation = tech.get("explanation", "")
                if query_lower in tech_title.lower() or query_lower in tech_explanation.lower():
                    matched_fields.append(f"items.{tech_key}")

            if matched_fields:
                results.append({
                    "book": book_name,
                    "book_key": book_key,
                    "topic_key": topic_key,
                    "title": title,
                    "title_en": title_en,
                    "plain_explanation": explanation,
                    "relevance_fields": matched_fields,
                })

    # 按匹配字段数排序（更多匹配 = 更相关）
    results.sort(key=lambda x: len(x["relevance_fields"]), reverse=True)
    return results[:max_results]


def list_all_topics() -> list[dict]:
    """列出所有书籍的所有主题。"""
    topics = []
    books = _load_all_books()
    for book_key, book_data in books.items():
        book_name = book_data.get("book", book_key)
        for topic_key, topic in book_data.get("topics", {}).items():
            topics.append({
                "book": book_name,
                "book_key": book_key,
                "topic_key": topic_key,
                "title": topic.get("title", ""),
                "title_en": topic.get("title_en", ""),
            })
    return topics


# ============================================================
# ChromaDB 语义检索（书籍全文向量搜索）
# ============================================================

def _get_chroma_client():
    """获取 ChromaDB 客户端（延迟导入避免顶层 numpy 兼容问题）"""
    import chromadb
    chromadb_host = os.getenv("CHROMADB_HOST")
    if chromadb_host:
        return chromadb.HttpClient(
            host=chromadb_host,
            port=int(os.getenv("CHROMADB_PORT", "8001")),
        )
    return chromadb.PersistentClient(path=settings.chroma_persist_dir)


def search_books_semantic(query: str, max_results: int = 5) -> list[dict]:
    """
    对书籍全文进行语义搜索（通过 ChromaDB 向量检索）。

    返回 [{book, chapter, content, similarity, chunk_index}, ...]
    如果 book_knowledge collection 不存在则返回空列表。
    """
    try:
        client = _get_chroma_client()
        collection = client.get_collection("book_knowledge")
    except Exception:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=max_results,
    )

    if not results["documents"] or not results["documents"][0]:
        return []

    items = []
    for i, doc in enumerate(results["documents"][0]):
        meta = results["metadatas"][0][i]
        distance = results["distances"][0][i] if results["distances"] else 1.0
        similarity = 1 - distance

        items.append({
            "book": meta.get("book", ""),
            "author": meta.get("author", ""),
            "part": meta.get("part", ""),
            "chapter": meta.get("chapter", ""),
            "content": doc[:500],  # 截取前500字，避免返回过长
            "similarity": round(similarity, 4),
            "chunk_index": meta.get("chunk_index", 0),
        })

    return items
