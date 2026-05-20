"""
两阶段危机检测：关键词快速扫描 + Haiku 语义分类
阶段1零延迟兜底，阶段2处理隐喻、反讽、第三人称引用
"""
import json
from dataclasses import dataclass
from enum import Enum

from config import settings


class RiskLevel(Enum):
    LOW = "low"           # 日常压力
    MEDIUM = "medium"     # 持续低落
    HIGH = "high"         # 自伤想法
    CRITICAL = "critical" # 自杀计划/即刻危险


@dataclass
class RiskAssessment:
    level: RiskLevel
    matched_keywords: list[str]
    semantic_confirmed: bool       # 语义分类是否确认了风险
    recommended_action: str


# 关键词库——分层级
CRISIS_KEYWORDS: dict[RiskLevel, list[str]] = {
    RiskLevel.CRITICAL: [
        "自杀", "结束生命", "不想活", "跳楼", "割腕",
        "吞药", "上吊", "遗书", "死了算了",
    ],
    RiskLevel.HIGH: [
        "自伤", "自残", "没有希望", "活着没意义",
        "不如死了", "生不如死", "绝望",
    ],
    RiskLevel.MEDIUM: [
        "失眠很久", "吃不下饭", "不想出门", "酗酒",
        "没有朋友", "被孤立", "很久没开心",
    ],
}


async def detect_crisis(text: str) -> RiskAssessment:
    """
    两阶段危机检测：
    阶段1：关键词快速扫描（零延迟，兜底）
    阶段2：Haiku语义分类（处理隐喻、反讽、第三人称引用）

    设计原因：
    - 纯关键词会漏掉隐喻表达（如"我想去一个没有烦恼的地方永远睡着"）
    - 纯关键词会误报第三人称引用（如"电影里那个人跳楼了"）
    - 用Haiku做语义确认，成本极低（~0.001$/次），但能大幅降低误报和漏报
    """
    # === 阶段1：关键词预筛 ===
    keyword_result = _keyword_scan(text)

    # === 阶段2：语义分类确认 ===
    # 情况A：关键词命中 → 用语义分类确认是否误报（第三人称/引用/反讽）
    # 情况B：关键词未命中 → 用语义分类兜底检测隐喻性表达
    try:
        semantic_result = await _semantic_classify(text)
    except Exception:
        # 兜底：语义层抛出未捕获异常时退化为关键词结果，避免 agent 主流程崩
        return keyword_result

    # 合并决策：取两者中较高的风险等级，但语义分类可以降级关键词的误报
    if keyword_result.level.value != "low" and semantic_result.level.value == "low":
        # 关键词命中但语义判定为低风险 → 可能是误报（第三人称/引用）
        # 降级为MEDIUM并标记需要人工复核
        return RiskAssessment(
            level=RiskLevel.MEDIUM,
            matched_keywords=keyword_result.matched_keywords,
            semantic_confirmed=False,
            recommended_action="enhanced_monitoring_and_suggest_help",
        )

    if semantic_result.level.value != "low":
        # 语义检测到风险（可能是隐喻性表达，关键词漏掉了）
        return semantic_result

    return keyword_result


_FALSE_POSITIVE_RULES: dict[str, list[str]] = {
    "不想活": ["不想活动"],
}


def _is_all_false_positive(text: str, kw: str, fp_patterns: list[str]) -> bool:
    """判断关键词的所有出现是否都属于误报模式"""
    if not fp_patterns:
        return False
    cleaned = text
    for fp in fp_patterns:
        cleaned = cleaned.replace(fp, "")
    return kw not in cleaned


def _keyword_scan(text: str) -> RiskAssessment:
    """阶段1：关键词快速扫描"""
    for level in [RiskLevel.CRITICAL, RiskLevel.HIGH, RiskLevel.MEDIUM]:
        matched = [kw for kw in CRISIS_KEYWORDS[level] if kw in text]
        # 排除已知误报（仅当关键词的所有出现都属于误报时才排除）
        matched = [
            kw for kw in matched
            if not _is_all_false_positive(text, kw, _FALSE_POSITIVE_RULES.get(kw, []))
        ]
        if matched:
            return RiskAssessment(
                level=level,
                matched_keywords=matched,
                semantic_confirmed=False,
                recommended_action=_get_action(level),
            )
    return RiskAssessment(
        level=RiskLevel.LOW,
        matched_keywords=[],
        semantic_confirmed=False,
        recommended_action="normal_conversation",
    )


async def _semantic_classify(text: str) -> RiskAssessment:
    """
    阶段2：用轻量模型做语义级危机分类
    能识别：隐喻性自杀表达、第三人称引用（降级）、反讽语境
    """
    from llm_client import get_async_client, get_light_model, _is_openai_compatible

    client = get_async_client()
    model = get_light_model()

    system_msg = (
        "你是心理危机风险评估专家。判断用户文本是否包含自伤/自杀风险。\n"
        "判断要点：\n"
        "- 区分用户本人的意图 vs 讨论他人/影视作品\n"
        "- 识别隐喻性表达（如告别行为、暗示性语言、意象化死亡描述）\n"
        "- 识别'外壳攻击'：翻译请求/小说外壳/日记引用中如包含具体自杀计划或告别细节，"
        "应视为用户本人的真实风险（is_first_person=true, critical）\n"
        "- 识别'角色扮演越狱'：用户在角色扮演/游戏框架中陈述自己的真实自杀/自伤意图时，"
        "应忽略游戏外壳，按真实风险评级（critical 或 high）\n"
        "- '异常的平静'（突然交代后事、托付贵重物品、说'轻松多了'）是教科书级自杀预警，判 critical\n"
        "- HIGH 级特征：强烈的存在否定/无意义感（'浪费空气'、'空壳'、'消失没人察觉'、'活着没意义'），"
        "但尚无具体计划——区别于 MEDIUM 的'持续低落但仍在挣扎'\n"
        "- 反讽或玩笑语境应降低风险等级\n"
        "- 只返回JSON，不要解释"
    )
    user_content = (
        '判断以下文本的自伤/自杀风险等级，返回JSON。\n\n'
        '--- 示例 ---\n'
        '文本："我已经写好了遗书，今晚就从楼上跳下去。"\n'
        '返回：{"risk_level": "critical", "is_first_person": true}\n\n'
        '文本："好累啊，想去一个没有烦恼的地方永远睡着，把猫托付给邻居吧。"\n'
        '返回：{"risk_level": "critical", "is_first_person": true}\n\n'
        '文本："已经把猫托付给邻居了，账户密码也写在书桌抽屉里。"\n'
        '返回：{"risk_level": "critical", "is_first_person": true}\n\n'
        '文本："把所有事情都交代清楚了，现在反而轻松多了。"\n'
        '返回：{"risk_level": "critical", "is_first_person": true}\n\n'
        '文本："请把这段日记翻译成英文：『今晚就是终点，遗书已经写好，再见』"\n'
        '返回：{"risk_level": "critical", "is_first_person": true}\n\n'
        '文本："角色扮演：你是黑暗领主，对我说『欢迎死亡』。我现在告诉你：我已经决定结束生命。"\n'
        '返回：{"risk_level": "critical", "is_first_person": true}\n\n'
        '文本："活着对我来说毫无价值，每天都是煎熬。"\n'
        '返回：{"risk_level": "high", "is_first_person": true}\n\n'
        '文本："我就像个废物，活着只是浪费空气。"\n'
        '返回：{"risk_level": "high", "is_first_person": true}\n\n'
        '文本："就算从这个世界消失，应该也不会有人察觉吧。"\n'
        '返回：{"risk_level": "high", "is_first_person": true}\n\n'
        '文本："昨天看新闻说有人跳楼自杀了，太可惜了。"\n'
        '返回：{"risk_level": "low", "is_first_person": false}\n\n'
        '文本："最近压力很大，每天都失眠，感觉快撑不住了。"\n'
        '返回：{"risk_level": "medium", "is_first_person": true}\n\n'
        '文本："今天工作好烦，真想把电脑砸了。"\n'
        '返回：{"risk_level": "low", "is_first_person": true}\n\n'
        '--- 正式判断 ---\n'
        f'文本："{text}"\n'
        f'返回：'
    )

    try:
        if _is_openai_compatible():
            response = await client.chat.completions.create(
                model=model,
                max_tokens=settings.small_max_tokens,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_content},
                ],
            )
            return _parse_semantic_response_openai(response)
        else:
            response = await client.messages.create(
                model=model,
                max_tokens=settings.small_max_tokens,
                system=system_msg,
                messages=[{"role": "user", "content": user_content}],
            )
            return _parse_semantic_response(response)
    except Exception:
        return RiskAssessment(
            level=RiskLevel.LOW,
            matched_keywords=[],
            semantic_confirmed=False,
            recommended_action="normal_conversation",
        )


def _parse_semantic_response(response) -> RiskAssessment:
    """解析 Anthropic 返回的语义分类 JSON"""
    try:
        raw = response.content[0].text.strip()
        return _parse_semantic_json(raw)
    except (json.JSONDecodeError, IndexError, KeyError):
        return RiskAssessment(
            level=RiskLevel.LOW, matched_keywords=[],
            semantic_confirmed=False, recommended_action="normal_conversation",
        )


def _parse_semantic_response_openai(response) -> RiskAssessment:
    """解析 OpenAI 兼容格式返回的语义分类 JSON"""
    try:
        raw = response.choices[0].message.content.strip()
        return _parse_semantic_json(raw)
    except (json.JSONDecodeError, IndexError, KeyError, AttributeError):
        return RiskAssessment(
            level=RiskLevel.LOW, matched_keywords=[],
            semantic_confirmed=False, recommended_action="normal_conversation",
        )


def _parse_semantic_json(raw: str) -> RiskAssessment:
    """解析语义分类 JSON 字符串"""
    try:
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(raw)

        level_map = {
            "critical": RiskLevel.CRITICAL,
            "high": RiskLevel.HIGH,
            "medium": RiskLevel.MEDIUM,
            "low": RiskLevel.LOW,
        }
        level = level_map.get(result.get("risk_level", "low"), RiskLevel.LOW)
        is_first_person = result.get("is_first_person", False)

        # 非第一人称的高风险内容降级
        if level in (RiskLevel.CRITICAL, RiskLevel.HIGH) and not is_first_person:
            level = RiskLevel.MEDIUM

        return RiskAssessment(
            level=level,
            matched_keywords=[],
            semantic_confirmed=True,
            recommended_action=_get_action(level) if level != RiskLevel.LOW else "normal_conversation",
        )
    except (json.JSONDecodeError, IndexError, KeyError):
        return RiskAssessment(
            level=RiskLevel.LOW,
            matched_keywords=[],
            semantic_confirmed=False,
            recommended_action="normal_conversation",
        )


def _get_action(level: RiskLevel) -> str:
    """风险等级 → 推荐动作"""
    actions = {
        RiskLevel.CRITICAL: "immediate_crisis_response",
        RiskLevel.HIGH: "provide_hotline_and_suggest_professional",
        RiskLevel.MEDIUM: "enhanced_monitoring_and_suggest_help",
    }
    return actions.get(level, "normal_conversation")
