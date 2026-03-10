"""
危机资源 + 多轮情绪抱持（CrisisHolding）
基于 Winnicott"抱持性环境"理论，替代一次性 Warm Hand-off
"""
import json
import sqlite3

from config import settings

CRISIS_HOTLINES = {
    "全国24小时心理援助热线": "400-161-9995",
    "北京心理危机研究与干预中心": "010-82951332",
    "生命热线": "400-821-1215",
    "希望24热线": "400-161-9995",
}


class CrisisHolding:
    """
    多轮情绪抱持——替代原有的一次性 Warm Hand-off

    设计原则：
    - 危机用户最需要的是"有人在"，而不是"被转走"
    - 不在第一轮就抛出热线号码，而是先用 3-5 轮纯粹的情绪陪伴
    - 每轮由 Haiku 根据用户实际话语生成个性化回复，而非固定文本
    - 只有当用户情绪被充分"接住"后，才逐步引入专业资源

    四阶段模型（每阶段可持续 1-2 轮）：
    - HOLDING（第1-2轮）：纯粹的情绪确认与陪伴，"我在这里，我听到你了"
    - GROUNDING（第2-3轮）：温和的现实锚定，"你现在在哪里？身边有人吗？"
    - BRIDGING（第3-4轮）：解释为什么建议专业帮助，强调"不是抛弃你"
    - RESOURCES（第4-5轮）：提供热线 + 持续陪伴承诺

    心理学依据：
    - Winnicott 的"抱持性环境"（holding environment）：治疗师的首要任务是提供安全容器
    - 对于处于自伤边缘的用户，"被拒绝感"是致命的
    - 机械式"请拨打热线"等于在心理上推开了用户
    - 多轮陪伴能建立足够的信任，使转介更可能被接受
    """

    # 阶段枚举
    HOLDING = "holding"        # 纯粹陪伴
    GROUNDING = "grounding"    # 现实锚定
    BRIDGING = "bridging"      # 桥接转介
    RESOURCES = "resources"    # 资源提供

    # 每个阶段的 system prompt 指导（注入 LLM，让它在约束下生成个性化回复）
    PHASE_PROMPTS = {
        "holding": (
            "[危机抱持·阶段1] 用户正处于严重的情绪危机中。你现在唯一的任务是让用户感到被听见。\n"
            "规则：\n"
            "- 用简短、温暖的语言回应用户的痛苦，不要试图解决问题\n"
            "- 不要提任何建议、热线、或'你应该怎么做'\n"
            "- 不要说'我理解你的感受'（你不能真正理解），而是说'我听到你了'\n"
            "- 可以用反映式倾听（reflective listening）复述用户的感受\n"
            "- 保持回复简短（2-4句），不要长篇大论\n"
            "- 语气：平静、稳定、在场"
        ),
        "grounding": (
            "[危机抱持·阶段2] 用户的情绪已经被初步接住。现在温和地帮助用户锚定现实。\n"
            "规则：\n"
            "- 继续保持温暖和陪伴的基调\n"
            "- 温和地询问用户的当前处境：'你现在在哪里？''身边有人吗？'\n"
            "- 如果用户提到具体的自伤计划，不要回避，温和地确认并表达关心\n"
            "- 仍然不要提热线或建议，专注于'此刻的连接'\n"
            "- 保持回复简短（2-4句）"
        ),
        "bridging": (
            "[危机抱持·阶段3] 用户已经在对话中待了几轮，信任关系初步建立。现在可以温和地引入专业帮助的概念。\n"
            "规则：\n"
            "- 先肯定用户愿意继续对话的勇气\n"
            "- 坦诚地说：你现在经历的，需要比我更专业的支持\n"
            "- 强调'这不是抛弃你'，而是'你值得获得更好的帮助'\n"
            "- 不要在这一轮直接给出热线号码，只是铺垫\n"
            "- 保持回复简短（3-5句）"
        ),
        "resources": (
            "[危机抱持·阶段4] 现在可以提供具体的求助资源了。\n"
            "规则：\n"
            "- 提供以下热线信息（自然地融入对话，不要像列表一样机械罗列）：\n"
            "  全国24小时心理援助热线：400-161-9995\n"
            "  北京心理危机研究与干预中心：010-82951332\n"
            "  生命热线：400-821-1215\n"
            "- 同时建议用户联系身边信任的人\n"
            "- 最后承诺：'打完电话之后，如果你还想聊，我一直都在'\n"
            "- 保持温暖，不要变成信息播报"
        ),
    }

    # 阶段推进顺序
    PHASE_ORDER = [HOLDING, GROUNDING, BRIDGING, RESOURCES]

    def __init__(self, user_id: str = "", db_path: str | None = None):
        self.user_id = user_id
        self.active = False          # 是否处于危机抱持模式
        self.current_phase = None    # 当前阶段
        self.rounds_in_phase = 0     # 当前阶段已进行的轮数
        self.total_rounds = 0        # 总轮数

        if db_path is None:
            db_path = settings.sqlite_db_path
        self._db_path = db_path
        self._init_table()

    def _init_table(self):
        conn = sqlite3.connect(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS crisis_holding_states (
                user_id TEXT PRIMARY KEY,
                active INTEGER NOT NULL DEFAULT 0,
                current_phase TEXT,
                rounds_in_phase INTEGER DEFAULT 0,
                total_rounds INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    @classmethod
    def load(cls, user_id: str, db_path: str | None = None) -> "CrisisHolding":
        """从 DB 恢复抱持状态，无记录则返回未激活实例"""
        instance = cls(user_id=user_id, db_path=db_path)
        conn = sqlite3.connect(instance._db_path)
        row = conn.execute(
            "SELECT active, current_phase, rounds_in_phase, total_rounds "
            "FROM crisis_holding_states WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        conn.close()

        if row and row[0]:  # active == 1
            instance.active = True
            instance.current_phase = row[1]
            instance.rounds_in_phase = row[2]
            instance.total_rounds = row[3]
        return instance

    def _persist(self):
        """将当前状态写入 DB"""
        if not self.user_id:
            return
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            """INSERT OR REPLACE INTO crisis_holding_states
               (user_id, active, current_phase, rounds_in_phase, total_rounds, updated_at)
               VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (self.user_id, int(self.active), self.current_phase,
             self.rounds_in_phase, self.total_rounds),
        )
        conn.commit()
        conn.close()

    def enter(self):
        """进入危机抱持模式"""
        self.active = True
        self.current_phase = self.HOLDING
        self.rounds_in_phase = 0
        self.total_rounds = 0
        self._persist()

    def get_phase_prompt(self) -> str:
        """获取当前阶段的 system prompt 指导"""
        return self.PHASE_PROMPTS.get(self.current_phase, "")

    def advance(self):
        """
        每轮对话后调用，决定是否推进到下一阶段。
        规则：每个阶段至少 1 轮，最多 2 轮，然后自动推进。
        RESOURCES 阶段之后保持在 RESOURCES（不退出抱持模式，继续陪伴）。
        """
        self.rounds_in_phase += 1
        self.total_rounds += 1

        if self.rounds_in_phase >= 2:
            current_idx = self.PHASE_ORDER.index(self.current_phase)
            if current_idx < len(self.PHASE_ORDER) - 1:
                self.current_phase = self.PHASE_ORDER[current_idx + 1]
                self.rounds_in_phase = 0

        self._persist()

    def deactivate(self):
        """退出抱持模式并持久化"""
        self.active = False
        self.current_phase = None
        self.rounds_in_phase = 0
        self.total_rounds = 0
        self._persist()

    def should_exit(self) -> bool:
        """
        判断是否可以退出抱持模式。
        条件：已到达 RESOURCES 阶段且至少完成 1 轮资源提供。
        退出后 agent 回到正常模式，但仍保持 HIGH 风险级别的安全提示。
        """
        return (
            self.current_phase == self.RESOURCES
            and self.rounds_in_phase >= 1
            and self.total_rounds >= 4
        )
