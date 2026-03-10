"""
量表评估模块——加载标准化心理量表并管理评估流程
支持 PHQ-9、GAD-7 等量表的题目呈现、评分和安全检查
"""
import json
from pathlib import Path
from dataclasses import dataclass, field

# 量表 JSON 所在目录
_SCALES_DIR = Path(__file__).resolve().parent.parent / "data" / "scales"

# 缓存已加载的量表定义
_scale_cache: dict[str, dict] = {}


def load_scale(name: str) -> dict:
    """
    加载量表定义。name 如 "PHQ-9"、"GAD-7"。
    返回完整的量表 JSON 字典。
    """
    if name in _scale_cache:
        return _scale_cache[name]

    file_map = {
        "PHQ-9": "phq9.json",
        "GAD-7": "gad7.json",
        "PERMA": "perma.json",
        "SWLS": "swls.json",
        "GQ-6": "gq6.json",
    }
    filename = file_map.get(name)
    if not filename:
        raise ValueError(f"不支持的量表: {name}")

    path = _SCALES_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"量表文件不存在: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    _scale_cache[name] = data
    return data


@dataclass
class ScaleResult:
    """量表评估结果"""
    scale_name: str
    total_score: int
    max_score: int
    category: str          # none / mild / moderate / mod_severe / severe
    label: str             # 中文标签
    answers: list[int]     # 每题得分
    safety_alerts: list[dict] = field(default_factory=list)


def score_scale(name: str, answers: list[int]) -> ScaleResult:
    """
    计算量表总分并返回结构化结果。

    answers: 每题得分列表，顺序与量表 items 一致。
    """
    scale = load_scale(name)
    items = scale["items"]

    if len(answers) != len(items):
        raise ValueError(
            f"{name} 需要 {len(items)} 个回答，收到 {len(answers)} 个"
        )

    total = sum(answers)

    # 反向计分：reverse_items 中的题目需要翻转分数
    reverse_ids = scale.get("reverse_items", [])
    if reverse_ids:
        options = scale["options"]
        max_option = max(o["value"] for o in options)
        min_option = min(o["value"] for o in options)
        for rid in reverse_ids:
            idx = rid - 1  # item_id 从 1 开始
            if 0 <= idx < len(answers):
                original = answers[idx]
                reversed_val = (max_option + min_option) - original
                total += reversed_val - original  # 修正差值

    max_score = scale["scoring"]["total_max"]

    # 匹配分数区间
    category = "unknown"
    label = "未知"
    for r in scale["scoring"]["ranges"]:
        if r["min"] <= total <= r["max"]:
            category = r["category"]
            label = r["label"]
            break

    # 安全检查：检查 safety_items
    safety_alerts = []
    for si in scale.get("safety_items", []):
        item_idx = si["item_id"] - 1  # item_id 从 1 开始
        if item_idx < len(answers):
            item_score = answers[item_idx]
            # 解析触发条件（目前仅支持 "score > N"）
            if _check_trigger(item_score, si["trigger_condition"]):
                safety_alerts.append({
                    "item_id": si["item_id"],
                    "item_text": items[item_idx]["text"],
                    "score": item_score,
                    "action": si["action"],
                    "note": si.get("note", ""),
                })

    return ScaleResult(
        scale_name=name,
        total_score=total,
        max_score=max_score,
        category=category,
        label=label,
        answers=answers,
        safety_alerts=safety_alerts,
    )


def get_scale_intro(name: str) -> dict:
    """
    返回量表的介绍信息和第一题，用于启动评估。
    """
    scale = load_scale(name)
    first_item = scale["items"][0]
    return {
        "scale": name,
        "description": scale["description"],
        "instruction": scale["instruction"],
        "total_items": len(scale["items"]),
        "options": scale["options"],
        "current_item": {
            "id": first_item["id"],
            "text": first_item["text"],
            "index": 0,
        },
    }


def get_next_item(name: str, current_index: int) -> dict | None:
    """
    返回量表的下一题。如果已经是最后一题，返回 None。
    """
    scale = load_scale(name)
    next_idx = current_index + 1
    if next_idx >= len(scale["items"]):
        return None

    item = scale["items"][next_idx]
    return {
        "id": item["id"],
        "text": item["text"],
        "index": next_idx,
    }


def format_result_for_agent(result: ScaleResult) -> str:
    """
    将评估结果格式化为 JSON 字符串，供 Agent 工具返回使用。
    """
    data = {
        "scale": result.scale_name,
        "total_score": result.total_score,
        "max_score": result.max_score,
        "category": result.category,
        "label": result.label,
        "answers": result.answers,
    }
    if result.safety_alerts:
        data["safety_alerts"] = result.safety_alerts
        data["requires_safety_protocol"] = True
    return json.dumps(data, ensure_ascii=False)


def _check_trigger(score: int, condition: str) -> bool:
    """
    解析简单的触发条件字符串。
    支持格式: "score > N", "score >= N", "score == N"
    """
    condition = condition.strip()
    if condition.startswith("score"):
        expr = condition.replace("score", str(score))
        try:
            return bool(eval(expr))  # noqa: S307
        except Exception:
            return False
    return False
