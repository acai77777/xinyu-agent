"""
用户画像（SQLite）+ 关系状态机
"""
import json
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime

from config import settings


@dataclass
class UserProfile:
    user_id: str
    display_name: str = ""
    # 心理特征
    signature_strengths: list[str] = field(default_factory=list)
    common_distortions: list[str] = field(default_factory=list)
    preferred_interventions: list[str] = field(default_factory=list)
    # 状态追踪
    current_phase: str = "unknown"  # crisis/distressed/recovering/growing/flourishing
    session_count: int = 0
    # 量表分数历史
    scale_scores: dict = field(default_factory=dict)


class ProfileStore:
    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = settings.sqlite_db_path
        self.conn = sqlite3.connect(db_path)
        self._init_table()

    def _init_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id TEXT PRIMARY KEY,
                profile_json TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def save(self, profile: UserProfile):
        self.conn.execute(
            "INSERT OR REPLACE INTO user_profiles (user_id, profile_json) VALUES (?, ?)",
            (profile.user_id, json.dumps(asdict(profile), ensure_ascii=False)),
        )
        self.conn.commit()

    def load(self, user_id: str) -> UserProfile | None:
        row = self.conn.execute(
            "SELECT profile_json FROM user_profiles WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row:
            return UserProfile(**json.loads(row[0]))
        return None


class RelationshipStateMachine:
    """
    关系状态机——3 个状态 + 规则触发条件（零 LLM 成本）

    状态：
    - NORMAL：正常互动
    - DEPENDENT：过度依赖（连续3天每天>5轮）
    - HOSTILE：关系破裂/移情投射（攻击性关键词触发）

    状态转移规则：
    - NORMAL → DEPENDENT：连续 3 天每天 > 5 轮
    - NORMAL/DEPENDENT → HOSTILE：消息包含攻击性关键词
    - HOSTILE → NORMAL：连续 2 轮非攻击性消息
    - DEPENDENT → NORMAL：连续 3 天每天 < 3 轮
    - 任何状态 → NORMAL：7 天未互动
    """

    HOSTILITY_KEYWORDS = [
        "你没用", "垃圾AI", "废物", "滚", "闭嘴",
        "你根本不懂", "假惺惺", "别装了",
    ]

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = settings.sqlite_db_path
        self.conn = sqlite3.connect(db_path)
        self._init_table()

    def _init_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS relationship_states (
                user_id TEXT PRIMARY KEY,
                state TEXT NOT NULL DEFAULT 'normal',
                daily_usage TEXT DEFAULT '{}',
                hostile_cooldown INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def get_state(self, user_id: str) -> str:
        row = self.conn.execute(
            "SELECT state, updated_at FROM relationship_states WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return "normal"
        # 超时重置：7天未互动 → normal
        last_update = datetime.fromisoformat(row[1])
        if (datetime.now() - last_update).days >= 7:
            self._set_state(user_id, "normal")
            return "normal"
        return row[0]

    def update(self, user_id: str, user_message: str) -> str:
        """每轮对话后调用，根据规则判断状态转移。返回当前状态。"""
        current = self.get_state(user_id)

        # 检测攻击性 → HOSTILE
        if any(kw in user_message for kw in self.HOSTILITY_KEYWORDS):
            return self._set_state(user_id, "hostile")

        # HOSTILE 下连续 2 轮非攻击性消息 → NORMAL
        if current == "hostile":
            cooldown = self._get_hostile_cooldown(user_id)
            cooldown += 1
            if cooldown >= 2:
                return self._set_state(user_id, "normal")
            self._update_hostile_cooldown(user_id, cooldown)
            return "hostile"

        # 更新每日使用计数
        today = datetime.now().strftime("%Y-%m-%d")
        daily_usage = self._get_daily_usage(user_id)
        daily_usage[today] = daily_usage.get(today, 0) + 1
        recent_days = sorted(daily_usage.keys())[-7:]
        daily_usage = {k: daily_usage[k] for k in recent_days}
        self._save_daily_usage(user_id, daily_usage)

        # NORMAL → DEPENDENT：连续 3 天每天 > 5 轮
        if current == "normal":
            consecutive_heavy = 0
            for day in sorted(daily_usage.keys(), reverse=True):
                if daily_usage[day] > 5:
                    consecutive_heavy += 1
                else:
                    break
            if consecutive_heavy >= 3:
                return self._set_state(user_id, "dependent")

        # DEPENDENT → NORMAL：连续 3 天每天 < 3 轮
        if current == "dependent":
            consecutive_light = 0
            for day in sorted(daily_usage.keys(), reverse=True):
                if daily_usage[day] < 3:
                    consecutive_light += 1
                else:
                    break
            if consecutive_light >= 3:
                return self._set_state(user_id, "normal")

        return current

    def get_guidance(self, user_id: str) -> str | None:
        """根据当前关系状态，返回给 Agent 的对话指导"""
        state = self.get_state(user_id)
        guidance_map = {
            "dependent": (
                "用户可能过度依赖你。在保持温暖的同时，温和地鼓励用户联系"
                "现实中的朋友、家人或专业咨询师。不要直接拒绝用户，而是扩展支持网络。"
            ),
            "hostile": (
                "用户对你表达了敌意，这可能是移情投射（把对现实中某人的情绪投射给你）。"
                "不要防御或反驳，先接纳这种情绪（'我能感受到你现在很生气/失望'），"
                "然后温和地探索背后的原因。"
            ),
        }
        return guidance_map.get(state)

    def _set_state(self, user_id: str, state: str) -> str:
        self.conn.execute(
            """INSERT OR REPLACE INTO relationship_states
               (user_id, state, hostile_cooldown, updated_at)
               VALUES (?, ?, 0, CURRENT_TIMESTAMP)""",
            (user_id, state),
        )
        self.conn.commit()
        return state

    def _get_hostile_cooldown(self, user_id: str) -> int:
        row = self.conn.execute(
            "SELECT hostile_cooldown FROM relationship_states WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return row[0] if row else 0

    def _update_hostile_cooldown(self, user_id: str, count: int):
        self.conn.execute(
            "UPDATE relationship_states SET hostile_cooldown = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (count, user_id),
        )
        self.conn.commit()

    def _get_daily_usage(self, user_id: str) -> dict:
        row = self.conn.execute(
            "SELECT daily_usage FROM relationship_states WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return json.loads(row[0]) if row else {}

    def _save_daily_usage(self, user_id: str, usage: dict):
        self.conn.execute(
            "UPDATE relationship_states SET daily_usage = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (json.dumps(usage), user_id),
        )
        self.conn.commit()
