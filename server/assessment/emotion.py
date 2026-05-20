"""
情绪识别——作为Agent工具被调用
用 Haiku 做结构化情绪分类
"""
import json
from dataclasses import dataclass

from config import settings


@dataclass
class EmotionResult:
    primary_emotion: str         # 主要情绪
    intensity: int               # 强度 1-10
    secondary_emotions: list[str]  # 次要情绪
    valence: str                 # 积极 / 消极 / 中性


# 情绪分类体系（基于Ekman基本情绪 + 扩展）
EMOTION_CATEGORIES = {
    "negative": ["悲伤", "焦虑", "愤怒", "恐惧", "厌恶", "羞耻", "内疚", "孤独", "无助"],
    "positive": ["快乐", "感恩", "希望", "自豪", "平静", "好奇", "爱"],
    "neutral": ["困惑", "无聊", "疲惫"],
}


def assess_emotion(user_text: str) -> dict:
    """
    情绪评估——用轻量模型做结构化情绪分类。
    返回字典格式供 Agent 工具调用使用。
    """
    from llm_client import get_sync_client, get_light_model, _is_openai_compatible

    client = get_sync_client()
    model = get_light_model()

    # 动态构建情绪词表，确保 prompt 与 EMOTION_CATEGORIES 同步
    neg_emotions = "、".join(EMOTION_CATEGORIES["negative"])
    pos_emotions = "、".join(EMOTION_CATEGORIES["positive"])
    neu_emotions = "、".join(EMOTION_CATEGORIES["neutral"])

    system_msg = (
        "你是情绪分析专家。分析用户文本的情绪，返回JSON格式。"
        "必须使用中文输出所有字段，包括情绪名称。"
        "valence 字段使用中文：积极 / 消极 / 中性。\n"
        "primary_emotion 和 secondary_emotions 必须从以下情绪词表中选取：\n"
        f"消极：{neg_emotions}\n"
        f"积极：{pos_emotions}\n"
        f"中性：{neu_emotions}"
    )
    user_content = (
        '分析以下文本的情绪状态，返回JSON。\n\n'
        '--- 示例 ---\n'
        '文本："我最近总是睡不着，感觉什么都做不好，活着好累。"\n'
        '返回：{"primary_emotion": "无助", "intensity": 8, '
        '"secondary_emotions": ["悲伤", "疲惫"], "valence": "消极"}\n\n'
        '文本："今天终于通过了考试，太开心了！感谢一直陪伴我的朋友们。"\n'
        '返回：{"primary_emotion": "快乐", "intensity": 9, '
        '"secondary_emotions": ["感恩", "自豪"], "valence": "积极"}\n\n'
        '文本："不知道接下来该怎么选，两个方向都有道理。"\n'
        '返回：{"primary_emotion": "困惑", "intensity": 5, '
        '"secondary_emotions": [], "valence": "中性"}\n\n'
        '--- 正式分析 ---\n'
        f'文本："{user_text}"\n'
        f'返回：'
    )

    try:
        if _is_openai_compatible():
            response = client.chat.completions.create(
                model=model,
                max_tokens=settings.small_max_tokens,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_content},
                ],
            )
            raw = response.choices[0].message.content.strip()
        else:
            response = client.messages.create(
                model=model,
                max_tokens=settings.small_max_tokens,
                system=system_msg,
                messages=[{"role": "user", "content": user_content}],
            )
            raw = response.content[0].text.strip()
        return _parse_emotion_raw(raw)
    except Exception:
        return {
            "primary_emotion": "未知",
            "intensity": 5,
            "secondary_emotions": [],
            "valence": "中性",
        }


def _parse_emotion_raw(raw: str) -> dict:
    """解析情绪分类 JSON 字符串"""
    try:
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(raw)
        # 兜底：LLM 偶尔输出英文 valence，统一映射为中文
        _valence_to_cn = {
            "positive": "积极", "negative": "消极", "neutral": "中性",
        }
        raw_valence = result.get("valence", "中性")
        valence = _valence_to_cn.get(raw_valence, raw_valence)
        return {
            "primary_emotion": result.get("primary_emotion", "未知"),
            "intensity": min(10, max(1, int(result.get("intensity", 5)))),
            "secondary_emotions": result.get("secondary_emotions", []),
            "valence": valence,
        }
    except (json.JSONDecodeError, IndexError, KeyError, ValueError):
        return {
            "primary_emotion": "未知",
            "intensity": 5,
            "secondary_emotions": [],
            "valence": "中性",
        }


def _parse_emotion_response(response) -> dict:
    """兼容旧接口：从 Anthropic response 对象中提取文本后解析"""
    raw = response.content[0].text.strip()
    return _parse_emotion_raw(raw)
