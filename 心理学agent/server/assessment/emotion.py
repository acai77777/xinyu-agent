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
    valence: str                 # positive / negative / neutral


# 情绪分类体系（基于Ekman基本情绪 + 扩展）
EMOTION_CATEGORIES = {
    "negative": ["悲伤", "焦虑", "愤怒", "恐惧", "厌恶", "羞耻", "内疚", "孤独", "无助"],
    "positive": ["快乐", "感恩", "希望", "自豪", "平静", "好奇", "爱"],
    "neutral": ["困惑", "无聊", "疲惫"],
}


def assess_emotion(user_text: str) -> dict:
    """
    情绪评估——用 Haiku 做结构化情绪分类。
    返回字典格式供 Agent 工具调用使用。
    """
    import anthropic
    client = anthropic.Anthropic()

    try:
        response = client.messages.create(
            model=settings.light_model,
            max_tokens=256,
            system="你是情绪分析专家。分析用户文本的情绪，返回JSON格式。",
            messages=[{
                "role": "user",
                "content": (
                    f'分析以下文本的情绪状态，返回JSON：\n'
                    f'文本："{user_text}"\n\n'
                    f'返回格式：\n'
                    f'{{"primary_emotion": "情绪名", "intensity": 1-10, '
                    f'"secondary_emotions": [], "valence": "positive/negative/neutral"}}'
                ),
            }],
        )
        return _parse_emotion_response(response)
    except Exception:
        return {
            "primary_emotion": "未知",
            "intensity": 5,
            "secondary_emotions": [],
            "valence": "neutral",
        }


def _parse_emotion_response(response) -> dict:
    """解析 Haiku 返回的情绪分类 JSON"""
    try:
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(raw)
        return {
            "primary_emotion": result.get("primary_emotion", "未知"),
            "intensity": min(10, max(1, int(result.get("intensity", 5)))),
            "secondary_emotions": result.get("secondary_emotions", []),
            "valence": result.get("valence", "neutral"),
        }
    except (json.JSONDecodeError, IndexError, KeyError, ValueError):
        return {
            "primary_emotion": "未知",
            "intensity": 5,
            "secondary_emotions": [],
            "valence": "neutral",
        }
