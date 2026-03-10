"""
认知扭曲检测——基于15种认知扭曲
采用混合策略：关键词预筛 + LLM精确分类
"""
import json
from dataclasses import dataclass

from config import settings


@dataclass
class DistortionResult:
    detected: bool
    distortion_type: str       # 扭曲类型（中文）
    distortion_name_en: str    # 英文名
    evidence: str              # 文本中的证据
    confidence: float          # 置信度 0-1


# 关键词预筛表——15种认知扭曲
KEYWORD_PATTERNS = {
    "all_or_nothing": {
        "name": "全或无思维",
        "name_en": "All-or-Nothing Thinking",
        "keywords": ["总是", "从不", "完全", "一点也不", "永远不会", "百分之百"],
    },
    "overgeneralization": {
        "name": "过度概括",
        "name_en": "Overgeneralization",
        "keywords": ["每次都", "永远", "所有人", "没有人", "从来都是"],
    },
    "catastrophizing": {
        "name": "灾难化",
        "name_en": "Catastrophizing",
        "keywords": ["最糟糕的", "万一", "完蛋了", "天塌了", "毁了"],
    },
    "mind_reading": {
        "name": "读心术",
        "name_en": "Mind Reading",
        "keywords": ["他肯定觉得", "他们一定在想", "别人都认为"],
    },
    "fortune_telling": {
        "name": "预言家谬误",
        "name_en": "Fortune Telling",
        "keywords": ["肯定会", "一定会失败", "不可能成功"],
    },
    "should_statements": {
        "name": "应该陈述",
        "name_en": "Should Statements",
        "keywords": ["我应该", "不应该", "必须", "不得不", "理应"],
    },
    "labeling": {
        "name": "贴标签",
        "name_en": "Labeling",
        "keywords": ["我就是个", "他就是", "这种人"],
    },
    "personalization": {
        "name": "个人化",
        "name_en": "Personalization",
        "keywords": ["都是我的错", "因为我", "怪我"],
    },
    "emotional_reasoning": {
        "name": "情绪推理",
        "name_en": "Emotional Reasoning",
        "keywords": ["我觉得所以", "感觉就是", "我感到所以一定"],
    },
    "mental_filter": {
        "name": "心理过滤",
        "name_en": "Mental Filter",
        "keywords": ["只看到", "全是坏的", "没有一点好的"],
    },
    "disqualifying_positive": {
        "name": "否定正面",
        "name_en": "Disqualifying the Positive",
        "keywords": ["不算", "只是因为", "运气好而已", "只是客气"],
    },
    "minimization": {
        "name": "最小化",
        "name_en": "Minimization",
        "keywords": ["没什么大不了", "不算什么", "谁都能做到"],
    },
    "control_fallacy": {
        "name": "控制谬误",
        "name_en": "Control Fallacy",
        "keywords": ["我控制不了", "都是我造成的", "无能为力"],
    },
    "fairness_fallacy": {
        "name": "公平谬误",
        "name_en": "Fallacy of Fairness",
        "keywords": ["不公平", "应该对等", "凭什么"],
    },
    "blaming": {
        "name": "指责",
        "name_en": "Blaming",
        "keywords": ["都怪", "都是因为你", "都赖"],
    },
}


def detect_distortion(user_text: str) -> list[DistortionResult]:
    """
    两阶段检测：
    1. 关键词预筛——快速、零成本，但有误报
    2. LLM精确分类——仅对预筛命中的进行确认，降低成本
    """
    # 阶段1：关键词预筛
    candidates = []
    for dist_type, info in KEYWORD_PATTERNS.items():
        for kw in info["keywords"]:
            if kw in user_text:
                candidates.append(dist_type)
                break

    if not candidates:
        return []

    # 阶段2：LLM确认（仅对候选项）
    return _llm_confirm_distortions(user_text, candidates)


def _llm_confirm_distortions(
    user_text: str, candidates: list[str]
) -> list[DistortionResult]:
    """用 Haiku 对关键词预筛候选进行语义确认，降低误报"""
    import anthropic
    client = anthropic.Anthropic()

    candidate_info = []
    for c in candidates:
        info = KEYWORD_PATTERNS[c]
        candidate_info.append(f"- {info['name']}（{info['name_en']}）")
    candidate_text = "\n".join(candidate_info)

    try:
        response = client.messages.create(
            model=settings.light_model,
            max_tokens=512,
            system="你是认知行为疗法（CBT）专家。判断用户文本中是否真的存在以下候选认知扭曲。",
            messages=[{
                "role": "user",
                "content": (
                    f'用户文本："{user_text}"\n\n'
                    f'候选认知扭曲：\n{candidate_text}\n\n'
                    f'判断要点：\n'
                    f'- 关键词存在不等于认知扭曲存在（如"我总是很开心"不是全或无思维）\n'
                    f'- 需要结合语境判断是否为非理性思维模式\n'
                    f'- "应该"在日常用语中很常见，只有当它表达不合理的自我要求时才是认知扭曲\n\n'
                    f'返回JSON数组，每个确认的扭曲包含：\n'
                    f'[{{"type": "扭曲类型中文名", "type_en": "英文名", '
                    f'"evidence": "文本中的证据", "confidence": 0-1}}]\n'
                    f'如果都不是真正的认知扭曲，返回空数组 []'
                ),
            }],
        )
        return _parse_distortion_response(response, candidates)
    except Exception:
        # LLM 调用失败时，返回低置信度的关键词预筛结果
        results = []
        for c in candidates:
            info = KEYWORD_PATTERNS[c]
            results.append(DistortionResult(
                detected=True,
                distortion_type=info["name"],
                distortion_name_en=info["name_en"],
                evidence="关键词预筛命中（LLM确认失败）",
                confidence=0.3,
            ))
        return results


def _parse_distortion_response(
    response, candidates: list[str]
) -> list[DistortionResult]:
    """解析 Haiku 返回的认知扭曲确认结果"""
    try:
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        items = json.loads(raw)

        if not isinstance(items, list):
            return []

        results = []
        for item in items:
            results.append(DistortionResult(
                detected=True,
                distortion_type=item.get("type", ""),
                distortion_name_en=item.get("type_en", ""),
                evidence=item.get("evidence", ""),
                confidence=min(1.0, max(0.0, float(item.get("confidence", 0.5)))),
            ))
        return results
    except (json.JSONDecodeError, IndexError, KeyError, ValueError):
        return []
