"""
记忆写入入口 —— 把对话中的关键信息持久化到三个记忆存储。

设计要点：
- record_emotion_snapshot：每轮调用，依赖 sub_agent 已有的情绪分析，零额外 LLM 成本
- finalize_session_memory：会话结束/达到阈值时调用，跑一次 LLM 抽取关键事实 + 画像
- 所有写入失败必须静默降级，绝不阻断聊天主流程
"""
import asyncio
import json
import logging
from datetime import datetime

from config import settings

logger = logging.getLogger(__name__)


# 触发会话结束写入的最低对话量（少于此值认为信息密度不足，跳过 LLM 调用）
_MIN_USEFUL_USER_CHARS = 30
_MIN_USEFUL_USER_TURNS = 2


# ====================================================================
# 每轮调用：写一条情绪快照到叙事记忆
# ====================================================================

async def record_emotion_snapshot(
    user_id: str,
    session_id: str,
    primary_emotion: str,
    intensity: int,
    trigger: str,
    theme: str | None = None,
) -> None:
    """
    异步写入叙事快照。

    主题策略：优先使用 session_notes.presenting_issue（外部传入），
    无主题时回退到 primary_emotion 本身——同情绪自然聚合成一条弧线。
    """
    if not user_id or not primary_emotion:
        return

    effective_theme = (theme or primary_emotion).strip()[:50]
    safe_trigger = (trigger or "").strip()[:100]
    try:
        safe_intensity = max(1, min(10, int(intensity)))
    except (TypeError, ValueError):
        safe_intensity = 5

    def _write_sync():
        from memory.narrative import NarrativeMemory, EmotionSnapshot
        nm = NarrativeMemory()
        snap = EmotionSnapshot(
            timestamp=datetime.now().isoformat(),
            primary_emotion=primary_emotion,
            intensity=safe_intensity,
            trigger=safe_trigger,
            session_id=session_id or "",
        )
        nm.add_snapshot(user_id, effective_theme, snap)

    try:
        await asyncio.to_thread(_write_sync)
    except Exception as e:
        logger.warning(f"[Memory] snapshot write failed: {e}")


# ====================================================================
# 会话结束：LLM 抽取关键事实 + 画像 → 写 Chroma + user_profiles
# ====================================================================

def _history_is_meaningful(history: list[dict]) -> bool:
    """对话内容是否有足够信息密度值得抽取。"""
    user_msgs = [
        m for m in history
        if m.get("role") == "user" and isinstance(m.get("content"), str)
    ]
    if len(user_msgs) < _MIN_USEFUL_USER_TURNS:
        return False
    total_chars = sum(len(m["content"].strip()) for m in user_msgs)
    return total_chars >= _MIN_USEFUL_USER_CHARS


async def _extract_session_memory(history: list[dict]) -> dict:
    """
    跑一次轻量模型，从对话中抽取：
    - profile_updates: 用户画像增量（display_name/phase/strengths/distortions/preferred_interventions）
    - key_facts: 值得长期记住的关键事实（每条 1 句话，用于语义检索）

    抽取失败返回空结构，调用方负责降级。
    """
    from llm_client import get_async_client, get_light_model, _is_openai_compatible, get_deepseek_extra_body

    transcript_parts = []
    for m in history[-30:]:
        role = m.get("role", "")
        content = m.get("content", "")
        if not isinstance(content, str):
            continue
        label = "用户" if role == "user" else "AI"
        transcript_parts.append(f"{label}：{content[:300]}")
    transcript = "\n".join(transcript_parts)

    system_msg = (
        "你是心理咨询档案整理员。根据本次对话提取需要长期记忆的信息。"
        "中文输出。不要使用 markdown 代码块。"
    )
    user_content = (
        f"对话记录：\n{transcript}\n\n"
        f"请直接返回 JSON：\n"
        f"{{\n"
        f'  "profile_updates": {{\n'
        f'    "display_name": "用户希望被称呼的名字，没有就空串",\n'
        f'    "current_phase": "crisis/distressed/recovering/growing/flourishing 中之一，未明显则空串",\n'
        f'    "signature_strengths": ["从对话中观察到的性格优势"],\n'
        f'    "common_distortions": ["认知扭曲类型，如灾难化/全或无思维"],\n'
        f'    "preferred_interventions": ["用户接受度高的干预方式"]\n'
        f'  }},\n'
        f'  "key_facts": ["值得跨会话记住的关键事实，每条单独一句，最多5条"]\n'
        f"}}\n"
        f"规则：只填能从对话中明确推断的内容，无法判断的字段留空数组或空串。"
    )

    client = get_async_client()
    model = get_light_model()
    if _is_openai_compatible():
        response = await client.chat.completions.create(
            model=model,
            max_tokens=settings.medium_max_tokens,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_content},
            ],
            extra_body=get_deepseek_extra_body(),
        )
        raw = response.choices[0].message.content.strip()
    else:
        response = await client.messages.create(
            model=model,
            max_tokens=settings.medium_max_tokens,
            system=system_msg,
            messages=[{"role": "user", "content": user_content}],
        )
        raw = response.content[0].text.strip()

    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    return json.loads(raw)


def _merge_profile(user_id: str, updates: dict) -> None:
    """把 updates 合并到现有 profile，列表字段去重追加。"""
    from memory.user_profile import ProfileStore, UserProfile

    ps = ProfileStore()
    profile = ps.load(user_id) or UserProfile(user_id=user_id)

    new_name = (updates.get("display_name") or "").strip()
    if new_name:
        profile.display_name = new_name

    new_phase = (updates.get("current_phase") or "").strip()
    if new_phase in ("crisis", "distressed", "recovering", "growing", "flourishing"):
        profile.current_phase = new_phase

    for field_name in ("signature_strengths", "common_distortions", "preferred_interventions"):
        incoming = updates.get(field_name) or []
        if not isinstance(incoming, list):
            continue
        existing = getattr(profile, field_name) or []
        merged = list(dict.fromkeys([*existing, *[str(x).strip() for x in incoming if str(x).strip()]]))
        setattr(profile, field_name, merged[:10])

    profile.session_count = (profile.session_count or 0) + 1
    ps.save(profile)


def _store_key_facts(user_id: str, key_facts: list[str]) -> None:
    """把关键事实写入 Chroma 语义记忆。"""
    from memory.semantic import SemanticMemory
    sm = SemanticMemory()
    for fact in key_facts:
        fact = str(fact).strip()
        if 5 <= len(fact) <= 300:
            sm.store(user_id, fact, memory_type="insight")


async def finalize_session_memory(
    user_id: str,
    session_id: str,
    history: list[dict],
) -> None:
    """
    会话结束时调用：抽取画像 + 关键事实，写入持久化记忆。

    门槛：用户消息少于 2 条或总字数少于 30 → 跳过，避免 LLM 浪费 + 垃圾写入。
    所有失败静默降级。
    """
    if not user_id or not history:
        return
    if not _history_is_meaningful(history):
        return

    try:
        extracted = await _extract_session_memory(history)
    except Exception as e:
        logger.warning(f"[Memory] session extraction failed: {e}")
        return

    profile_updates = extracted.get("profile_updates") or {}
    key_facts = extracted.get("key_facts") or []

    if profile_updates:
        try:
            await asyncio.to_thread(_merge_profile, user_id, profile_updates)
        except Exception as e:
            logger.warning(f"[Memory] profile merge failed: {e}")

    if key_facts:
        try:
            await asyncio.to_thread(_store_key_facts, user_id, key_facts)
        except Exception as e:
            logger.warning(f"[Memory] key facts store failed: {e}")

    logger.info(
        f"[Memory] session {session_id[:8] if session_id else 'anon'} finalized: "
        f"profile_updated={bool(profile_updates)} facts={len(key_facts)}"
    )
