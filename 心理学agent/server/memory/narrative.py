"""
叙事记忆——追踪用户情感演变轨迹

与语义记忆的区别：
- 语义记忆：存储离散的"事实快照"
- 叙事记忆：存储连续的"情感故事线"
"""
import json
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime

from config import settings
from assessment.emotion import EMOTION_CATEGORIES


def _emotion_score(emotion_name: str, intensity: int) -> float:
    """将 (情绪名, 强度) 转为有向分数：积极→+intensity，消极→-intensity，中性/未知→0"""
    if emotion_name in EMOTION_CATEGORIES["positive"]:
        return float(intensity)
    elif emotion_name in EMOTION_CATEGORIES["negative"]:
        return float(-intensity)
    return 0.0


@dataclass
class EmotionSnapshot:
    """单次情绪快照"""
    timestamp: str
    primary_emotion: str
    intensity: int          # 1-10
    trigger: str            # 触发事件摘要
    session_id: str


@dataclass
class NarrativeArc:
    """情感叙事弧线——一段连续的情感经历"""
    arc_id: str
    user_id: str
    theme: str              # 主题（如"失恋"、"工作压力"）
    started_at: str
    last_updated: str
    snapshots: list[EmotionSnapshot]
    arc_summary: str        # LLM 生成的叙事摘要
    trend: str              # improving | worsening | fluctuating | stable


class NarrativeMemory:
    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = settings.sqlite_db_path
        self.conn = sqlite3.connect(db_path)
        self._init_table()

    def _init_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS narrative_arcs (
                arc_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                theme TEXT NOT NULL,
                started_at TEXT NOT NULL,
                last_updated TEXT NOT NULL,
                snapshots_json TEXT NOT NULL DEFAULT '[]',
                arc_summary TEXT DEFAULT '',
                trend TEXT DEFAULT 'stable',
                is_active INTEGER DEFAULT 1
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_narrative_user
            ON narrative_arcs(user_id, is_active)
        """)
        self.conn.commit()

    def add_snapshot(self, user_id: str, theme: str, snapshot: EmotionSnapshot) -> str:
        """
        向叙事弧线添加情绪快照。
        该主题已有活跃弧线则追加，否则创建新弧线。
        """
        import uuid
        arc = self._get_active_arc(user_id, theme)

        if arc is None:
            arc_id = str(uuid.uuid4())
            now = datetime.now().isoformat()
            self.conn.execute(
                """INSERT INTO narrative_arcs
                   (arc_id, user_id, theme, started_at, last_updated, snapshots_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (arc_id, user_id, theme, now, now, json.dumps([asdict(snapshot)])),
            )
        else:
            arc_id = arc["arc_id"]
            snapshots = json.loads(arc["snapshots_json"])
            snapshots.append(asdict(snapshot))
            snapshots = snapshots[-30:]  # 只保留最近 30 个快照
            self.conn.execute(
                """UPDATE narrative_arcs
                   SET snapshots_json = ?, last_updated = ?
                   WHERE arc_id = ?""",
                (json.dumps(snapshots), datetime.now().isoformat(), arc_id),
            )

        self.conn.commit()
        return arc_id

    async def update_narrative_summary(self, arc_id: str, force: bool = False):
        """
        叙事摘要生成——按需生成，非每次快照都调 LLM。

        触发条件：
        - force=True
        - 快照数达到 5 的倍数
        - 上次摘要为空
        """
        arc = self._get_arc_by_id(arc_id)
        if not arc:
            return

        snapshots = json.loads(arc["snapshots_json"])
        if len(snapshots) < 2:
            return

        # 规则引擎：用有向分数计算趋势（积极→正，消极→负）
        scores = [
            _emotion_score(s.get("primary_emotion", ""), s.get("intensity", 5))
            for s in snapshots
        ]
        diff = scores[-1] - scores[0]

        if diff > 2:
            trend = "improving"
        elif diff < -2:
            trend = "worsening"
        else:
            # |diff| <= 2：看中间波动方向
            directions = [scores[i + 1] - scores[i] for i in range(len(scores) - 1)]
            has_up = any(d > 0 for d in directions)
            has_down = any(d < 0 for d in directions)
            trend = "fluctuating" if (has_up and has_down) else "stable"

        # 判断是否需要调 LLM 生成详细摘要
        need_llm = (
            force
            or not arc.get("arc_summary")
            or len(snapshots) % 5 == 0
        )

        summary = arc.get("arc_summary", "")

        if need_llm:
            from llm_client import get_async_client, get_light_model, _is_openai_compatible, get_deepseek_extra_body

            client = get_async_client()
            model = get_light_model()

            timeline = "\n".join([
                f"- {s['timestamp']}: {s['primary_emotion']}(强度{s['intensity']}/10) 触发：{s['trigger']}"
                for s in snapshots[-10:]
            ])

            system_msg = (
                "你是心理咨询记录分析师。根据用户的情绪时间线，生成简洁的叙事摘要。"
                "必须使用中文输出所有内容。不要使用 markdown 代码块包裹 JSON。"
            )
            user_content = (
                f"主题：{arc['theme']}\n"
                f"情绪时间线：\n{timeline}\n\n"
                f"请直接返回JSON（不要用```包裹）：\n"
                f'{{"summary": "用第三人称描述这段情感经历的演变（2-3句话）", '
                f'"trend": "improving/worsening/fluctuating/stable"}}\n\n'
                f"--- 示例 ---\n"
                f"时间线：焦虑(8) → 焦虑(6) → 平静(4)\n"
                f'{{"summary": "用户从高强度焦虑逐步缓解，最终趋于平静，情绪整体好转。", "trend": "improving"}}\n\n'
                f"时间线：快乐(7) → 悲伤(5) → 快乐(6) → 焦虑(4)\n"
                f'{{"summary": "用户情绪在积极与消极之间反复切换，尚未形成稳定状态。", "trend": "fluctuating"}}\n\n'
                f"--- 正式分析 ---\n"
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
                        extra_body=get_deepseek_extra_body(),
                    )
                    raw_text = response.choices[0].message.content.strip()
                else:
                    response = await client.messages.create(
                        model=model,
                        max_tokens=settings.small_max_tokens,
                        system=system_msg,
                        messages=[{"role": "user", "content": user_content}],
                    )
                    raw_text = response.content[0].text.strip()
                result = json.loads(raw_text)
                summary = result.get("summary", summary)
                # 融合策略：规则引擎有方向性判断时以规则为准，否则采纳 LLM 意见
                llm_trend = result.get("trend")
                if trend in ("stable", "fluctuating") and llm_trend in (
                    "improving", "worsening", "fluctuating", "stable",
                ):
                    trend = llm_trend
            except Exception:
                # LLM 失败时用规则引擎生成模板摘要
                emotions = [s["primary_emotion"] for s in snapshots]
                unique_emotions = "、".join(list(dict.fromkeys(emotions))[:5])
                summary = (
                    f"用户围绕「{arc['theme']}」经历了{len(snapshots)}次情绪记录，"
                    f"主要情绪包括{unique_emotions}，整体趋势{trend}。"
                )

        self.conn.execute(
            "UPDATE narrative_arcs SET arc_summary = ?, trend = ? WHERE arc_id = ?",
            (summary, trend, arc_id),
        )
        self.conn.commit()

    def get_narrative_context(self, user_id: str) -> str | None:
        """
        获取用户的叙事上下文——注入 Agent 的 system prompt。
        返回最近 3 条活跃叙事弧线的摘要。
        """
        arcs = self.conn.execute(
            """SELECT theme, started_at, last_updated, arc_summary, trend, snapshots_json
               FROM narrative_arcs
               WHERE user_id = ? AND is_active = 1
               ORDER BY last_updated DESC LIMIT 3""",
            (user_id,),
        ).fetchall()

        if not arcs:
            return None

        trend_cn = {
            "improving": "好转中",
            "worsening": "恶化中",
            "fluctuating": "波动中",
            "stable": "稳定",
        }

        lines = []
        for theme, started, updated, summary, trend, snaps_json in arcs:
            snapshots = json.loads(snaps_json)
            days = (datetime.fromisoformat(updated) - datetime.fromisoformat(started)).days
            last_snap = snapshots[-1] if snapshots else None

            line = f"主题'{theme}'（第{days}天，趋势：{trend_cn.get(trend, '未知')}）"
            if last_snap:
                line += f"，上次情绪：{last_snap['primary_emotion']}({last_snap['intensity']}/10)"
            if summary:
                line += f"。{summary}"
            lines.append(line)

        return "[叙事记忆] " + " | ".join(lines)

    def _get_active_arc(self, user_id: str, theme: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM narrative_arcs WHERE user_id = ? AND theme = ? AND is_active = 1",
            (user_id, theme),
        ).fetchone()
        if row:
            cols = [
                "arc_id", "user_id", "theme", "started_at", "last_updated",
                "snapshots_json", "arc_summary", "trend", "is_active",
            ]
            return dict(zip(cols, row))
        return None

    def _get_arc_by_id(self, arc_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM narrative_arcs WHERE arc_id = ?", (arc_id,),
        ).fetchone()
        if row:
            cols = [
                "arc_id", "user_id", "theme", "started_at", "last_updated",
                "snapshots_json", "arc_summary", "trend", "is_active",
            ]
            return dict(zip(cols, row))
        return None
