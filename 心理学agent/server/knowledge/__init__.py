"""
知识库模块——心理教育材料与练习模板
"""
from knowledge.exercises import get_exercise, list_exercises, get_exercises_by_category
from knowledge.psychoeducation import (
    get_psychoeducation,
    get_distortion_explanation,
    list_topics,
)

__all__ = [
    "get_exercise",
    "list_exercises",
    "get_exercises_by_category",
    "get_psychoeducation",
    "get_distortion_explanation",
    "list_topics",
]
