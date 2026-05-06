"""
知识库模块——心理教育材料、练习模板与书籍知识库
"""
from knowledge.exercises import get_exercise, list_exercises, get_exercises_by_category
from knowledge.psychoeducation import (
    get_psychoeducation,
    get_distortion_explanation,
    list_topics,
)
from knowledge.knowledge_base import (
    get_topic,
    get_plain_explanation,
    search_knowledge,
    list_all_topics,
    search_books_semantic,
)

__all__ = [
    "get_exercise",
    "list_exercises",
    "get_exercises_by_category",
    "get_psychoeducation",
    "get_distortion_explanation",
    "list_topics",
    "get_topic",
    "get_plain_explanation",
    "search_knowledge",
    "list_all_topics",
    "search_books_semantic",
]
