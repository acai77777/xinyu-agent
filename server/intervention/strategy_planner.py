"""
策略规划器——整个系统的核心路由
基于"阶段化整合模型"，用确定性规则（非LLM）决定干预策略
"""
from dataclasses import dataclass
from enum import Enum


class UserPhase(Enum):
    CRISIS = "crisis"           # 危机阶段 → 安全守护接管
    DISTRESSED = "distressed"   # 困扰阶段 → CBT为主
    DIFFUSE = "diffuse"         # 弥散性情绪阶段 → 倾听优先，不急于分类
    RECOVERING = "recovering"   # 恢复阶段 → CBT+积极心理学并重
    GROWING = "growing"         # 成长阶段 → 积极心理学为主
    FLOURISHING = "flourishing" # 繁荣阶段 → 积极心理学


@dataclass
class InterventionPlan:
    phase: UserPhase
    primary_approach: str        # "cbt" / "positive_psychology" / "safety" / "active_listening"
    recommended_techniques: list[str]
    conversation_guidance: str   # 给LLM的对话指导


READINESS_SIGNALS = {
    "resistant": [
        "别跟我说这些", "不想做练习", "没用的", "不要建议",
        "我不需要", "别给我讲道理", "不想做", "别分析我",
    ],
    "ready": [
        "帮我想想办法", "我该怎么办", "有什么方法", "想试试",
        "可以做些什么", "怎么才能", "我想改变", "教我",
        "有没有什么练习", "想想办法", "怎么办",
    ],
    "exploring": [
        "为什么会这样", "是不是因为", "我在想", "也许是",
        "会不会是", "我不确定",
    ],
}


def detect_user_readiness(user_messages: list[str]) -> str:
    """
    从最近的用户消息中检测干预准备程度。

    扫描最近 5 条用户消息（越近权重越高），按优先级：
    resistant > ready > exploring > unknown

    返回: "resistant" | "ready" | "exploring" | "unknown"
    """
    recent = user_messages[-5:]
    for msg in reversed(recent):
        for kw in READINESS_SIGNALS["resistant"]:
            if kw in msg:
                return "resistant"
        for kw in READINESS_SIGNALS["ready"]:
            if kw in msg:
                return "ready"
        for kw in READINESS_SIGNALS["exploring"]:
            if kw in msg:
                return "exploring"
    return "unknown"


def plan_intervention(
    emotion_state: str,
    distortion_type: str = "",
    session_count: int = 0,
    user_readiness: str = "unknown",
) -> InterventionPlan:
    """
    根据用户状态决定干预策略。

    路由逻辑：
    - 危机 → 安全守护（已在Agent循环前置处理）
    - 困扰（负面情绪+认知扭曲）→ CBT为主
    - 恢复（负面情绪减轻）→ CBT+积极心理学
    - 正常/积极 → 积极心理学为主

    user_readiness 参数（用户主导模式）：
    - "unknown"：尚未确认用户意愿 → 先倾听，不主动推干预
    - "exploring"：用户在探索中，可以温和引导
    - "ready"：用户明确表达想要改变 → 启动结构化干预
    - "resistant"：用户抗拒干预 → 回退到纯倾听模式
    """
    if emotion_state == "crisis":
        return InterventionPlan(
            phase=UserPhase.CRISIS,
            primary_approach="safety",
            recommended_techniques=["crisis_response"],
            conversation_guidance="立即启动安全协议，提供危机热线。",
        )

    # === 用户主导模式：未确认意愿或抗拒时，不主动推干预 ===
    if user_readiness in ("unknown", "resistant"):
        if emotion_state in ("distressed", "diffuse"):
            return InterventionPlan(
                phase=UserPhase.DIFFUSE if emotion_state == "diffuse" else UserPhase.DISTRESSED,
                primary_approach="active_listening",
                recommended_techniques=[
                    "reflective_listening",
                    "emotional_validation",
                    "open_exploration",
                ],
                conversation_guidance="\n".join([
                    "用户尚未准备好接受结构化干预。你的首要任务是倾听和陪伴。",
                    "- 使用反映式倾听（'听起来你感到...'）",
                    "- 验证情绪的合理性（'有这样的感受是完全可以理解的'）",
                    "- 不要主动分析认知扭曲，不要推荐练习",
                    "- 可以在合适时机温和地询问：'你现在最需要什么？是有人听你说，还是想一起想想办法？'",
                    "- 用户的回答决定下一步：如果选择'听我说'→继续倾听；如果选择'想办法'→转入引导模式",
                    "- 如果用户抗拒干预（user_readiness=resistant），绝不要再次推荐，尊重用户的节奏",
                ]),
            )

    if emotion_state == "distressed":
        techniques = []
        guidance = ""
        if distortion_type:
            techniques.append("cognitive_restructuring")
            techniques.append("socratic_questioning")
            guidance = (
                f"用户已准备好探索。检测到'{distortion_type}'认知模式。"
                f"使用苏格拉底式提问温和引导：先共情，再探索证据和反证，最后引导替代视角。"
                f"注意：不要告诉用户他有'认知扭曲'，用日常语言引导。"
            )
        else:
            techniques.append("behavioral_activation")
            techniques.append("relaxation")
            guidance = (
                "用户已准备好接受引导。优先共情倾听，然后提供选项让用户选择："
                "'你想试试一个放松练习，还是我们一起想想可以做些什么让自己好受一点？'"
            )

        return InterventionPlan(
            phase=UserPhase.DISTRESSED,
            primary_approach="cbt",
            recommended_techniques=techniques,
            conversation_guidance=guidance,
        )

    if emotion_state == "normal":
        return InterventionPlan(
            phase=UserPhase.GROWING,
            primary_approach="positive_psychology",
            recommended_techniques=["gratitude", "strength_spotting", "flow"],
            conversation_guidance="用户状态稳定，适合引入积极心理学干预。可以引导感恩练习、优势发现或心流探索。",
        )

    # positive
    return InterventionPlan(
        phase=UserPhase.FLOURISHING,
        primary_approach="positive_psychology",
        recommended_techniques=["meaning_exploration", "best_possible_self", "savoring"],
        conversation_guidance="用户状态积极，可以深入探索人生意义、最佳可能自我，或引导品味当下的积极体验。",
    )
