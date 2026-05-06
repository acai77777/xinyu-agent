"""
结构化会话笔记——LLM 的外部工作记忆

将分散的 6 层上下文信息统一为结构化对象，按需生成紧凑提示。
分三层：用户层（跨会话持久）、会话层（单次会话）、实时层（当前轮次）。

冷启动策略：
- is_warm() == False 时回退到 loop.py 的原有全量注入
- is_warm() == True  时使用 to_compact_prompt()（<500 token）
"""
import asyncio
import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SessionNotes:
    """结构化会话笔记"""

    # --- 用户层（跨会话持久）---
    user_profile_summary: str = ""
    relationship_state: str = "normal"
    narrative_trend: str = ""
    narrative_context: str = ""

    # --- 会话层（单次会话）---
    presenting_issue: str = ""
    session_strategy: str = ""
    key_moments: list[str] = field(default_factory=list)
    interventions_used: list[str] = field(default_factory=list)

    # --- 实时层（当前轮次，由工具结果更新）---
    safety_level: str = "safe"
    recent_emotion: str = ""
    active_distortions: list[str] = field(default_factory=list)

    # --- 元数据 ---
    _session_id: str = ""
    _user_id: str = ""
    _turn_count: int = 0

    def is_warm(self) -> bool:
        """
        判断笔记是否已预热（信息充足以支撑紧凑模式）。

        条件（满足任一即可）：
        - 有核心议题（策略已生成，通常第2-3轮）
        - 有用户画像 且 已对话 ≥3 轮（老用户新会话）
        """
        has_issue = bool(self.presenting_issue)
        has_profile = bool(self.user_profile_summary)
        has_turns = self._turn_count >= 3
        return has_issue or (has_profile and has_turns)

    def to_compact_prompt(self) -> str:
        """
        生成紧凑的上下文提示（目标 <500 token）。
        仅在 is_warm() == True 时调用。
        """
        lines: list[str] = []

        if self.safety_level != "safe":
            lines.append(f"[安全等级] {self.safety_level}")

        if self.user_profile_summary:
            lines.append(f"[用户画像] {self.user_profile_summary}")

        if self.presenting_issue:
            lines.append(f"[核心议题] {self.presenting_issue}")

        if self.session_strategy:
            lines.append(f"[会话策略] {self.session_strategy}")

        if self.narrative_trend and self.narrative_trend != "stable":
            trend_cn = {
                "improving": "好转中",
                "worsening": "恶化中",
                "fluctuating": "波动中",
            }
            lines.append(
                f"[情感趋势] {trend_cn.get(self.narrative_trend, self.narrative_trend)}"
            )

        if self.narrative_context:
            lines.append(self.narrative_context)

        if self.key_moments:
            lines.append(f"[关键时刻] {'；'.join(self.key_moments[-3:])}")

        if self.recent_emotion:
            lines.append(f"[近期情绪] {self.recent_emotion}")

        if self.active_distortions:
            lines.append(f"[认知模式] {'、'.join(self.active_distortions)}")

        if self.relationship_state != "normal":
            state_cn = {"dependent": "过度依赖", "hostile": "关系张力"}
            lines.append(
                f"[关系注意] {state_cn.get(self.relationship_state, self.relationship_state)}"
            )

        return "\n".join(lines)


# ====================================================================
# 异步加载
# ====================================================================

async def load_or_create(
    session_id: str, user_id: str, turn_count: int,
) -> SessionNotes:
    """
    从各个数据源异步加载数据，组装 SessionNotes。
    所有同步 DB 调用都通过 asyncio.to_thread 包装，避免阻塞事件循环。
    """
    notes = SessionNotes(
        _session_id=session_id,
        _user_id=user_id,
        _turn_count=turn_count,
    )

    # 并行加载四个数据源
    results = await asyncio.gather(
        _load_profile(user_id),
        _load_narrative(user_id),
        _load_relationship(user_id),
        _load_strategy(session_id),
        return_exceptions=True,
    )

    profile_data, narrative_data, relationship_data, strategy_data = results

    # 用户画像
    if isinstance(profile_data, dict):
        notes.user_profile_summary = profile_data.get("summary", "")

    # 叙事记忆
    if isinstance(narrative_data, dict):
        notes.narrative_trend = narrative_data.get("trend", "")
        notes.narrative_context = narrative_data.get("context", "")

    # 关系状态
    if isinstance(relationship_data, str):
        notes.relationship_state = relationship_data

    # 会话策略
    if isinstance(strategy_data, dict):
        notes.presenting_issue = strategy_data.get("presenting_issue", "")
        notes.session_strategy = strategy_data.get("strategy_summary", "")

    return notes


# ====================================================================
# 各数据源加载器（同步调用 → asyncio.to_thread）
# ====================================================================

async def _load_profile(user_id: str) -> dict:
    """加载用户画像，返回 {"summary": "..."}"""
    def _sync():
        from memory.user_profile import ProfileStore
        ps = ProfileStore()
        profile = ps.load(user_id)
        if not profile:
            return {"summary": ""}

        parts = []
        if profile.display_name:
            parts.append(profile.display_name)
        if profile.current_phase and profile.current_phase != "unknown":
            phase_cn = {
                "crisis": "危机期", "distressed": "困扰期",
                "recovering": "恢复期", "growing": "成长期",
                "flourishing": "蓬勃期",
            }
            parts.append(f"阶段:{phase_cn.get(profile.current_phase, profile.current_phase)}")
        if profile.signature_strengths:
            parts.append(f"优势:{'、'.join(profile.signature_strengths[:3])}")
        if profile.common_distortions:
            parts.append(f"认知扭曲:{'、'.join(profile.common_distortions[:3])}")
        if profile.preferred_interventions:
            parts.append(f"偏好干预:{'、'.join(profile.preferred_interventions[:2])}")
        return {"summary": "；".join(parts)}

    return await asyncio.to_thread(_sync)


async def _load_narrative(user_id: str) -> dict:
    """加载叙事记忆，返回 {"trend": "...", "context": "..."}"""
    def _sync():
        from memory.narrative import NarrativeMemory
        nm = NarrativeMemory()
        ctx = nm.get_narrative_context(user_id)
        # 从最新弧线提取趋势
        arcs = nm.conn.execute(
            """SELECT trend FROM narrative_arcs
               WHERE user_id = ? AND is_active = 1
               ORDER BY last_updated DESC LIMIT 1""",
            (user_id,),
        ).fetchone()
        trend = arcs[0] if arcs else ""
        return {"trend": trend, "context": ctx or ""}

    return await asyncio.to_thread(_sync)


async def _load_relationship(user_id: str) -> str:
    """加载关系状态，返回状态字符串"""
    def _sync():
        from memory.user_profile import RelationshipStateMachine
        rsm = RelationshipStateMachine()
        return rsm.get_state(user_id)

    return await asyncio.to_thread(_sync)


async def _load_strategy(session_id: str) -> dict:
    """加载会话策略，返回 {"presenting_issue": "...", "strategy_summary": "..."}"""
    from agent.session_strategy import load_session_strategy
    strategy = await load_session_strategy(session_id)
    if not strategy:
        return {"presenting_issue": "", "strategy_summary": ""}

    goals = "→".join(strategy.stage_goals[:2]) if strategy.stage_goals else ""
    techniques = "、".join(strategy.techniques[:3]) if strategy.techniques else ""
    summary = f"{strategy.primary_approach}"
    if goals:
        summary += f"：{goals}"
    if techniques:
        summary += f"（{techniques}）"

    return {
        "presenting_issue": strategy.presenting_issue,
        "strategy_summary": summary,
    }
