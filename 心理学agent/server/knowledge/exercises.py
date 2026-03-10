"""
练习模板库——统一管理所有心理练习的获取与分类
整合感恩练习（gratitude.py）、JSON 数据文件和认知重构模板
"""
import json
from pathlib import Path

from intervention.positive.gratitude import GRATITUDE_EXERCISES
from intervention.positive.strengths import VIA_STRENGTHS, STRENGTH_DISCOVERY_PROMPTS
from intervention.cbt.cognitive_restructuring import ThoughtRecord

# JSON 练习数据目录
_EXERCISES_DIR = Path(__file__).resolve().parent.parent / "data" / "exercises"

# 练习分类映射
_EXERCISE_CATEGORIES = {
    "gratitude_journal":      "positive",
    "mental_subtraction":     "positive",
    "gratitude_letter":       "positive",
    "strength_spotting":      "positive",
    "best_possible_self":     "positive",
    "mindful_breathing":      "wellness",
    "progressive_relaxation": "wellness",
    "thought_record":         "cbt",
    "behavioral_activation":  "cbt",
}


def _load_json_exercise(exercise_type: str) -> dict | None:
    """从 data/exercises/ 加载 JSON 练习模板"""
    filepath = _EXERCISES_DIR / f"{exercise_type}.json"
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def get_exercise(exercise_type: str) -> dict | None:
    """
    获取指定类型的练习模板。
    返回包含 name / instruction / follow_up_prompts 的字典，
    thought_record 额外包含 total_steps。
    未找到返回 None。
    """
    # 感恩练习库
    if exercise_type in GRATITUDE_EXERCISES:
        ex = GRATITUDE_EXERCISES[exercise_type]
        return {
            "exercise_type": exercise_type,
            "category": _EXERCISE_CATEGORIES.get(exercise_type, "positive"),
            "name": ex["name"],
            "instruction": ex["instruction"],
            "follow_up_prompts": ex["follow_up_prompts"],
        }

    # 七栏思维记录
    if exercise_type == "thought_record":
        tr = ThoughtRecord()
        return {
            "exercise_type": "thought_record",
            "category": "cbt",
            "name": "思维记录（七栏法）",
            "instruction": tr.get_next_prompt(),
            "total_steps": 7,
        }

    # JSON 数据文件
    data = _load_json_exercise(exercise_type)
    if data:
        return {
            "exercise_type": exercise_type,
            "category": _EXERCISE_CATEGORIES.get(exercise_type, "other"),
            "name": data["name"],
            "instruction": data["instruction"],
            "follow_up_prompts": data.get("follow_up_prompts", []),
        }

    return None


def list_exercises() -> list[dict]:
    """
    列出所有可用练习。
    返回 [{exercise_type, name, category}, ...] 的列表。
    """
    exercises = []

    # 感恩练习
    for etype, ex in GRATITUDE_EXERCISES.items():
        exercises.append({
            "exercise_type": etype,
            "name": ex["name"],
            "category": _EXERCISE_CATEGORIES.get(etype, "positive"),
        })

    # 七栏法
    exercises.append({
        "exercise_type": "thought_record",
        "name": "思维记录（七栏法）",
        "category": "cbt",
    })

    # JSON 文件中的练习
    json_types = [
        "mindful_breathing", "behavioral_activation",
        "strength_spotting", "best_possible_self", "progressive_relaxation",
    ]
    for etype in json_types:
        data = _load_json_exercise(etype)
        if data:
            exercises.append({
                "exercise_type": etype,
                "name": data["name"],
                "category": _EXERCISE_CATEGORIES.get(etype, "other"),
            })

    return exercises


def get_exercises_by_category(category: str) -> list[dict]:
    """
    按类别筛选练习。
    category: "cbt" / "positive" / "wellness"
    """
    return [ex for ex in list_exercises() if ex["category"] == category]
