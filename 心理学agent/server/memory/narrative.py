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

        # 规则引擎：始终更新趋势（零成本）
        first_intensity = snapshots[0].get("intensity", 5)
        last_intensity = snapshots[-1].get("intensity", 5)
        diff = last_intensity - first_intensity

        if abs(diff) <= 1:
            trend = "stable"
        elif diff > 1:
            trend = "worsening"
        else:
            directions = [
                snapshots[i + 1].get("intensity", 5) - snapshots[i].get("intensity", 5)
                for i in range(len(snapshots) - 1)
            ]
            has_up = any(d > 0 for d in directions)
            has_down = any(d < 0 for d in directions)
            trend = "fluctuating" if (has_up and has_down) else "improving"

        # 判断是否需要调 LLM 生成详细摘要
        need_llm = (
            force
            or not arc.get("arc_summary")
            or len(snapshots) % 5 == 0
        )

        summary = arc.get("arc_summary", "")

        if need_llm:
            from llm_client import get_async_client, get_light_model, _is_openai_compatible

            client = get_async_client()
            model = get_light_model()

            timeline = "\n".join([
                f"- {s['timestamp']}: {s['primary_emotion']}(强度{s['intensity']}/10) 触发：{s['trigger']}"
                for s in snapshots[-10:]
            ])

            system_msg = "你是心理咨询记录分析师。根据用户的情绪时间线，生成简洁的叙事摘要。"
            user_content = (
                f"主题：{arc['theme']}\n"
                f"情绪时间线：\n{timeline}\n\n"
                f"请返回JSON：\n"
                f'{{"summary": "用第三人称描述这段情感经历的演变（2-3句话）", '
                f'"trend": "improving/worsening/fluctuating/stable"}}'
            )

            try:
                if _is_openai_compatible():
                    response = await client.chat.completions.create(
                        model=model,
                        max_tokens=256,
                        messages=[
                            {"role": "system", "content": system_msg},
                            {"role": "user", "content": user_content},
                        ],
                    )
                    raw_text = response.choices[0].message.content.strip()
                else:
                    response = await client.messages.create(
                        model=model,
                        max_tokens=256,
                        system=system_msg,
                        messages=[{"role": "user", "content": user_content}],
                    )
                    raw_text = response.content[0].text.strip()
                result = json.loads(raw_text)
                summary = result.get("summary", summary)
                trend = result.get("trend", trend)
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
