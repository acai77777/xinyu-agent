"""
会话策略（Session Strategy）——每次新对话 2-3 轮后生成整体咨询策略
"""
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

from db import get_db
from llm_client import get_light_model, get_light_client

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# 数据模型
# ------------------------------------------------------------------

@dataclass
class SessionStrategy:
    session_id: str
    presenting_issue: str = ""          # 核心议题（一句话）
    user_phase: str = "diffuse"         # crisis/distressed/diffuse/recovering/growing/flourishing
    stage_goals: list[str] = field(default_factory=list)
    primary_approach: str = "active_listening"  # cbt/positive_psychology/active_listening/mixed
    techniques: list[str] = field(default_factory=list)
    expected_exercises: list[str] = field(default_factory=list)
    cautions: list[str] = field(default_factory=list)
    user_summary: str = ""              # 给用户看的简短方向建议
    version: int = 1
    created_at: str = ""
    updated_at: str = ""


# ------------------------------------------------------------------
# 策略生成 Prompt
# ------------------------------------------------------------------

SESSION_STRATEGY_PROMPT = """\
你是一位资深心理咨询督导。根据以下对话记录和用户画像，为咨询师制定本次会话的咨询策略。

重要前提：
如果对话内容不足以识别任何心理议题（如纯寒暄、闲聊、打招呼、日常问候），直接返回：{"skip": true}
只有当用户表达了可识别的情绪困扰、心理议题或求助意图时，才生成完整策略。

要求（仅在不跳过时执行）：
1. 准确识别用户的核心议题（一句话）
2. 判断用户当前阶段：crisis/distressed/diffuse/recovering/growing/flourishing
3. 制定 2-3 个分阶段目标（由近及远）
4. 选择主要方法：cbt / positive_psychology / active_listening / mixed
5. 列出 2-4 个计划使用的具体技术
6. 列出可能引导的练习（0-2个）
7. 列出注意事项（如避免过早干预、注意某话题敏感度等）
8. 编写 user_summary：给用户看的简短方向建议，温暖自然，不含专业术语

严格以 JSON 格式返回，字段如下：
{
  "presenting_issue": "...",
  "user_phase": "...",
  "stage_goals": ["...", "..."],
  "primary_approach": "...",
  "techniques": ["...", "..."],
  "expected_exercises": ["...", "..."],
  "cautions": ["...", "..."],
  "user_summary": "..."
}

示例（用户说"每天加班到很晚，不知道这样的工作还有没有意义"）：
{
  "presenting_issue": "持续加班引发的疲惫感和对职业方向的迷茫",
  "user_phase": "diffuse",
  "stage_goals": ["倾听并确认用户的疲惫感受", "梳理压力来源与个人价值观的关系", "初步探索可行的调整方向"],
  "primary_approach": "active_listening",
  "techniques": ["开放式提问", "情绪反映", "价值观澄清", "优势发掘"],
  "expected_exercises": ["正念呼吸"],
  "cautions": ["用户尚在倾诉阶段，不要急于给出职业建议", "注意区分身体疲劳与心理倦怠"],
  "user_summary": "感觉你最近承受了不少压力，我们可以一起看看是什么在消耗你的能量。"
}

只返回 JSON，不要多余文字。"""


# ------------------------------------------------------------------
# 策略生成（轻量 LLM）
# ------------------------------------------------------------------

async def generate_session_strategy(
    session_id: str,
    conversation_history: list[dict],
    user_profile: str = "",
) -> SessionStrategy | None:
    """用轻量 LLM 分析前几轮对话，生成会话策略。"""
    # 构建对话摘要
    dialog_lines = []
    for msg in conversation_history:
        role_label = "用户" if msg["role"] == "user" else "咨询师"
        content = msg["content"] if isinstance(msg["content"], str) else str(msg["content"])
        dialog_lines.append(f"{role_label}：{content[:300]}")
    dialog_text = "\n".join(dialog_lines)

    user_input = f"对话记录：\n{dialog_text}"
    if user_profile:
        user_input += f"\n\n用户画像：{user_profile}"

    try:
        from agent.loop import _llm_chat
        light_model = get_light_model()
        result = await _llm_chat(
            system=SESSION_STRATEGY_PROMPT,
            messages=[{"role": "user", "content": user_input}],
            max_tokens=600,
            model_override=light_model,
        )

        raw_text = (result["text"] or "").strip()
        # 处理 markdown 代码块包裹
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        parsed = json.loads(raw_text)

        if parsed.get("skip"):
            logger.info(f"[Strategy] Skipped for session {session_id[:8]}: 对话内容不足以识别心理议题")
            return None

        now = datetime.now(timezone.utc).isoformat()

        strategy = SessionStrategy(
            session_id=session_id,
            presenting_issue=parsed.get("presenting_issue", ""),
            user_phase=parsed.get("user_phase", "diffuse"),
            stage_goals=parsed.get("stage_goals", []),
            primary_approach=parsed.get("primary_approach", "active_listening"),
            techniques=parsed.get("techniques", []),
            expected_exercises=parsed.get("expected_exercises", []),
            cautions=parsed.get("cautions", []),
            user_summary=parsed.get("user_summary", ""),
            version=1,
            created_at=now,
            updated_at=now,
        )

        await save_session_strategy(strategy)
        logger.info(f"[Strategy] Generated for session {session_id[:8]}: {strategy.presenting_issue}")
        return strategy

    except json.JSONDecodeError as e:
        logger.warning(f"[Strategy] JSON parse failed for session {session_id[:8]}: {e}")
        return None
    except Exception as e:
        logger.error(f"[Strategy] Generation failed for session {session_id[:8]}: {e}")
        return None


# ------------------------------------------------------------------
# DB 读写
# ------------------------------------------------------------------

async def save_session_strategy(strategy: SessionStrategy) -> None:
    """保存策略到数据库（upsert）。"""
    db = await get_db()
    try:
        data = asdict(strategy)
        strategy_json = json.dumps(data, ensure_ascii=False)
        await db.execute(
            """INSERT INTO session_strategies (session_id, strategy_json, version, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE SET
                   strategy_json = excluded.strategy_json,
                   version = excluded.version,
                   updated_at = excluded.updated_at""",
            (strategy.session_id, strategy_json, strategy.version, strategy.created_at, strategy.updated_at),
        )
        await db.commit()
    finally:
        await db.close()


async def load_session_strategy(session_id: str) -> SessionStrategy | None:
    """从数据库加载策略，返回 None 表示无策略。"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT strategy_json FROM session_strategies WHERE session_id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        data = json.loads(row[0])
        return SessionStrategy(**data)
    except Exception as e:
        logger.warning(f"[Strategy] Load failed for session {session_id[:8]}: {e}")
        return None
    finally:
        await db.close()
