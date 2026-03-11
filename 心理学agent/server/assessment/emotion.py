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
    情绪评估——用轻量模型做结构化情绪分类。
    返回字典格式供 Agent 工具调用使用。
    """
    from llm_client import get_sync_client, get_light_model, _is_openai_compatible

    client = get_sync_client()
    model = get_light_model()

    system_msg = "你是情绪分析专家。分析用户文本的情绪，返回JSON格式。"
    user_content = (
        f'分析以下文本的情绪状态，返回JSON：\n'
        f'文本："{user_text}"\n\n'
        f'返回格式：\n'
        f'{{"primary_emotion": "情绪名", "intensity": 1-10, '
        f'"secondary_emotions": [], "valence": "positive/negative/neutral"}}'
    )

    try:
        if _is_openai_compatible():
            response = client.chat.completions.create(
                model=model,
                max_tokens=256,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_content},
                ],
            )
            raw = response.choices[0].message.content.strip()
        else:
            response = client.messages.create(
                model=model,
                max_tokens=256,
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
            "valence": "neutral",
        }


def _parse_emotion_raw(raw: str) -> dict:
    """解析情绪分类 JSON 字符串"""
    try:
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


def _parse_emotion_response(response) -> dict:
    """兼容旧接口：从 Anthropic response 对象中提取文本后解析"""
    raw = response.content[0].text.strip()
    return _parse_emotion_raw(raw)
