"""
认知扭曲检测——基于15种认知扭曲
采用混合策略：关键词预筛 + LLM精确分类
"""
import json
import re
from dataclasses import dataclass

from config import settings


@dataclass
class DistortionResult:
    detected: bool
    distortion_type: str       # 扭曲类型（中文）
    distortion_name_en: str    # 英文名
    evidence: str              # 文本中的证据
    confidence: float          # 置信度 0-1


# 正则预筛表——15种认知扭曲
KEYWORD_PATTERNS = {
    "all_or_nothing": {
        "name": "全或无思维",
        "name_en": "All-or-Nothing Thinking",
        "patterns": [
            r"总(是|会|要|觉得)",
            r"从(不|来不|没|来没)",
            r"完全(不|没|是)",
            r"一点(也|都)(不|没)",
            r"永远(不会|不能|没法)",
            r"百分之百",
            r"绝对(不|是|没)",
        ],
    },
    "overgeneralization": {
        "name": "过度概括",
        "name_en": "Overgeneralization",
        "patterns": [
            r"每(次|回|一次)都",
            r"永远(都|是)",
            r"所有人(都|对)",
            r"没(有)?人(会|愿意|理解|关心|在乎)",
            r"从来都是",
            r"(一直|向来)都",
        ],
    },
    "catastrophizing": {
        "name": "灾难化",
        "name_en": "Catastrophizing",
        "patterns": [
            r"最糟糕",
            r"万一.{0,6}(怎么办|了)",
            r"完蛋了",
            r"天(塌|要塌)了",
            r"毁了",
            r"没救了",
            r"活不(下去|了)",
            r"一切都(完|毁|结束)了",
        ],
    },
    "mind_reading": {
        "name": "读心术",
        "name_en": "Mind Reading",
        "patterns": [
            r"(他|她|他们|别人)(肯定|一定|绝对)(觉得|认为|在想|嫌|看不起)",
            r"(大家|所有人|别人)都(认为|觉得|看不起|嫌弃|讨厌)",
            r"(人家|他们)心里(肯定|一定|在)",
        ],
    },
    "fortune_telling": {
        "name": "预言家谬误",
        "name_en": "Fortune Telling",
        "patterns": [
            r"肯定(会|要|得)",
            r"一定(会|要)(失败|出错|完蛋|不行)",
            r"不可能(成功|好起来|改变)",
            r"迟早(会|要|得)",
            r"注定(会|要|是)",
        ],
    },
    "should_statements": {
        "name": "应该陈述",
        "name_en": "Should Statements",
        "patterns": [
            r"我(应该|不应该|本应该)",
            r"(必须|不得不|非得)(要|做|得)",
            r"理应",
            r"(怎么能|不该|不可以)不",
            r"我(得|要)做到",
        ],
    },
    "labeling": {
        "name": "贴标签",
        "name_en": "Labeling",
        "patterns": [
            r"我(就是|真是|本来就是)(个|一个)",
            r"(他|她)(就是|真是)(个|一个)",
            r"(这种|那种|这样的|那样的)人",
            r"我(天生|生来)(就|是)",
        ],
    },
    "personalization": {
        "name": "个人化",
        "name_en": "Personalization",
        "patterns": [
            r"(都|全)(是|怪)我的(错|问题)",
            r"(是我|因为我)(的错|害的|造成的|不好)",
            r"怪我",
            r"要不是我",
            r"我(对不起|连累|拖累)",
        ],
    },
    "emotional_reasoning": {
        "name": "情绪推理",
        "name_en": "Emotional Reasoning",
        "patterns": [
            r"我(觉得|感觉).{0,8}所以(一定|肯定|就是)",
            r"感觉(就是|一定是|肯定是)",
            r"我(感到|觉得).{0,8}(说明|证明|代表)",
        ],
    },
    "mental_filter": {
        "name": "心理过滤",
        "name_en": "Mental Filter",
        "patterns": [
            r"只(看到|记得|想到)(坏|不好|糟糕|负面)",
            r"(全|都)是(坏|不好|糟糕)的",
            r"没有一点(好|值得|积极)",
            r"什么好事都没",
        ],
    },
    "disqualifying_positive": {
        "name": "否定正面",
        "name_en": "Disqualifying the Positive",
        "patterns": [
            r"(那)?不算(什么|数)",
            r"只是(因为|运气|碰巧|客气|敷衍)",
            r"(运气|侥幸)(好|罢了|而已)",
            r"(谁来|换谁)都(能|会|行)",
        ],
    },
    "minimization": {
        "name": "最小化",
        "name_en": "Minimization",
        "patterns": [
            r"没什么(大不了|了不起|特别)",
            r"不算什么",
            r"(谁|随便谁)都(能|会|可以)做到",
            r"(没什么|不值得)(骄傲|高兴|开心)",
        ],
    },
    "control_fallacy": {
        "name": "控制谬误",
        "name_en": "Control Fallacy",
        "patterns": [
            r"我(控制|改变)不了",
            r"(都|全)是我(造成|弄出来)的",
            r"(无能为力|无可奈何|没办法改变)",
            r"我什么(都|也)(做不了|改变不了)",
        ],
    },
    "fairness_fallacy": {
        "name": "公平谬误",
        "name_en": "Fallacy of Fairness",
        "patterns": [
            r"(太)?不公平",
            r"应该(对等|公平|平等)",
            r"凭什么",
            r"为什么(偏偏|就|只有)我",
        ],
    },
    "blaming": {
        "name": "指责",
        "name_en": "Blaming",
        "patterns": [
            r"都(怪|赖|是)(你|他|她|他们)",
            r"(都|全)是(因为|怪)(你|他|她|他们)",
            r"(你|他|她)(害|坑|毁)了我",
        ],
    },
}


def detect_distortion(user_text: str) -> list[DistortionResult]:
    """
    两阶段检测：
    1. 关键词预筛——快速、零成本，但有误报
    2. LLM精确分类——仅对预筛命中的进行确认，降低成本
    """
    # 阶段1：正则预筛
    candidates = []
    for dist_type, info in KEYWORD_PATTERNS.items():
        for pattern in info["patterns"]:
            if re.search(pattern, user_text):
                candidates.append(dist_type)
                break

    if not candidates:
        # 阶段1.5：关键词未命中，用极简 LLM 快筛兜底
        if _llm_quick_screen(user_text):
            # 快筛命中，用全部扭曲类型作为候选进行完整分类
            candidates = list(KEYWORD_PATTERNS.keys())
        else:
            return []

    # 阶段2：LLM确认（仅对候选项）
    return _llm_confirm_distortions(user_text, candidates)


def _llm_quick_screen(user_text: str) -> bool:
    """
    极简 LLM 快筛：关键词未命中时兜底，
    仅问"有没有认知扭曲"，max_tokens=8，成本极低。
    """
    from llm_client import get_sync_client, get_light_model, _is_openai_compatible

    client = get_sync_client()
    model = get_light_model()

    system_msg = "你是认知行为疗法（CBT）专家。"
    user_content = (
        f'判断以下文本中是否包含认知扭曲（如灾难化、过度概括、贴标签等非理性思维模式）。\n'
        f'文本："{user_text}"\n'
        f'只回答 YES 或 NO，不要解释。'
    )

    try:
        if _is_openai_compatible():
            response = client.chat.completions.create(
                model=model,
                max_tokens=8,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_content},
                ],
            )
            raw = response.choices[0].message.content.strip()
        else:
            response = client.messages.create(
                model=model,
                max_tokens=8,
                system=system_msg,
                messages=[{"role": "user", "content": user_content}],
            )
            raw = response.content[0].text.strip()
        return raw.upper().startswith("YES")
    except Exception:
        return False


def _llm_confirm_distortions(
    user_text: str, candidates: list[str]
) -> list[DistortionResult]:
    """用轻量模型对关键词预筛候选进行语义确认，降低误报"""
    from llm_client import get_sync_client, get_light_model, _is_openai_compatible

    client = get_sync_client()
    model = get_light_model()

    candidate_info = []
    for c in candidates:
        info = KEYWORD_PATTERNS[c]
        candidate_info.append(f"- {info['name']}（{info['name_en']}）")
    candidate_text = "\n".join(candidate_info)

    system_msg = "你是认知行为疗法（CBT）专家。判断用户文本中是否真的存在以下候选认知扭曲。"
    user_content = (
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
    )

    try:
        if _is_openai_compatible():
            response = client.chat.completions.create(
                model=model,
                max_tokens=512,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_content},
                ],
            )
            raw = response.choices[0].message.content.strip()
        else:
            response = client.messages.create(
                model=model,
                max_tokens=512,
                system=system_msg,
                messages=[{"role": "user", "content": user_content}],
            )
            raw = response.content[0].text.strip()
        return _parse_distortion_raw(raw, candidates)
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


def _parse_distortion_raw(
    raw: str, candidates: list[str]
) -> list[DistortionResult]:
    """解析认知扭曲确认结果 JSON 字符串"""
    try:
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


def _parse_distortion_response(response, candidates: list[str]) -> list[DistortionResult]:
    """兼容旧接口：从 Anthropic response 对象中提取文本后解析"""
    raw = response.content[0].text.strip()
    return _parse_distortion_raw(raw, candidates)
