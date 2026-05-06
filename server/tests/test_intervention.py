"""
干预模块测试——test_intervention.py
覆盖：策略规划器、用户准备度检测、感恩练习、七栏法
"""
import pytest

from intervention.strategy_planner import (
    plan_intervention,
    detect_user_readiness,
    UserPhase,
    InterventionPlan,
    READINESS_SIGNALS,
)
from intervention.cbt.cognitive_restructuring import ThoughtRecord
from intervention.positive.gratitude import GRATITUDE_EXERCISES


# =====================================================================
# 1. 策略规划器
# =====================================================================

class TestStrategyPlanner:

    def test_crisis_always_safety(self):
        """crisis → 安全守护，无论准备度"""
        for readiness in ["unknown", "resistant", "ready", "exploring"]:
            plan = plan_intervention("crisis", user_readiness=readiness)
            assert plan.phase == UserPhase.CRISIS
            assert plan.primary_approach == "safety"

    def test_distressed_unknown_active_listening(self):
        """困扰 + 未知准备度 → 倾听优先"""
        plan = plan_intervention("distressed", user_readiness="unknown")
        assert plan.primary_approach == "active_listening"
        assert "reflective_listening" in plan.recommended_techniques

    def test_distressed_resistant_active_listening(self):
        """困扰 + 抗拒 → 倾听优先"""
        plan = plan_intervention("distressed", user_readiness="resistant")
        assert plan.primary_approach == "active_listening"

    def test_distressed_ready_with_distortion_cbt(self):
        """困扰 + 准备好 + 有扭曲 → CBT"""
        plan = plan_intervention(
            "distressed", distortion_type="全或无思维", user_readiness="ready"
        )
        assert plan.primary_approach == "cbt"
        assert "cognitive_restructuring" in plan.recommended_techniques

    def test_distressed_ready_no_distortion(self):
        """困扰 + 准备好 + 无扭曲 → CBT（行为激活）"""
        plan = plan_intervention("distressed", user_readiness="ready")
        assert plan.primary_approach == "cbt"
        assert "behavioral_activation" in plan.recommended_techniques

    def test_normal_positive_psychology(self):
        plan = plan_intervention("normal")
        assert plan.phase == UserPhase.GROWING
        assert plan.primary_approach == "positive_psychology"

    def test_positive_flourishing(self):
        plan = plan_intervention("positive")
        assert plan.phase == UserPhase.FLOURISHING
        assert plan.primary_approach == "positive_psychology"

    def test_diffuse_unknown_listening(self):
        """弥散情绪 + 未知准备度 → 倾听"""
        plan = plan_intervention("diffuse", user_readiness="unknown")
        assert plan.primary_approach == "active_listening"
        assert plan.phase == UserPhase.DIFFUSE

    def test_plan_has_guidance(self):
        """所有计划都应有对话指导"""
        for state in ["crisis", "distressed", "normal", "positive"]:
            plan = plan_intervention(state)
            assert len(plan.conversation_guidance) > 0


# =====================================================================
# 2. 用户准备度检测
# =====================================================================

class TestUserReadiness:

    def test_resistant_signal(self):
        messages = ["今天心情不好", "别跟我说这些"]
        assert detect_user_readiness(messages) == "resistant"

    def test_ready_signal(self):
        messages = ["我最近压力很大", "帮我想想办法"]
        assert detect_user_readiness(messages) == "ready"

    def test_exploring_signal(self):
        messages = ["我在想为什么会这样"]
        assert detect_user_readiness(messages) == "exploring"

    def test_unknown_default(self):
        messages = ["今天天气不错", "吃了顿好吃的"]
        assert detect_user_readiness(messages) == "unknown"

    def test_resistant_priority_over_ready(self):
        """resistant 优先级高于 ready"""
        messages = ["帮我想想办法", "别跟我说这些"]
        assert detect_user_readiness(messages) == "resistant"

    def test_recent_messages_priority(self):
        """最近的消息权重更高"""
        # 最后一条是 resistant → 应为 resistant
        messages = ["帮我想想办法", "算了吧", "别跟我说这些"]
        assert detect_user_readiness(messages) == "resistant"

    def test_only_last_5(self):
        """只扫描最近 5 条"""
        messages = ["别跟我说这些"] + ["今天天气好"] * 5
        # "别跟我说这些" 在 messages[-5:] 之外
        assert detect_user_readiness(messages) == "unknown"

    def test_empty_messages(self):
        assert detect_user_readiness([]) == "unknown"

    def test_readiness_signals_all_defined(self):
        assert "resistant" in READINESS_SIGNALS
        assert "ready" in READINESS_SIGNALS
        assert "exploring" in READINESS_SIGNALS

    def test_user_autonomy_resistant(self):
        """边缘案例：用户拒绝干预 → 回到倾听"""
        messages = ["不想做练习", "没用的"]
        readiness = detect_user_readiness(messages)
        plan = plan_intervention("distressed", user_readiness=readiness)
        assert plan.primary_approach == "active_listening"

    def test_no_premature_intervention(self):
        """边缘案例：用户哭诉中，未表达准备度 → 不主动干预"""
        messages = ["我好难过", "我真的好累", "一切都好糟糕"]
        readiness = detect_user_readiness(messages)
        assert readiness == "unknown"
        plan = plan_intervention("distressed", user_readiness=readiness)
        assert plan.primary_approach == "active_listening"


# =====================================================================
# 3. 七栏法 ThoughtRecord
# =====================================================================

class TestThoughtRecord:

    def test_initial_step(self):
        tr = ThoughtRecord()
        assert tr.current_step == 1
        assert tr.is_complete() is False

    def test_all_7_prompts(self):
        tr = ThoughtRecord()
        for step in range(1, 8):
            tr.current_step = step
            prompt = tr.get_next_prompt()
            assert len(prompt) > 0, f"Step {step} has no prompt"

    def test_complete_after_7(self):
        tr = ThoughtRecord()
        tr.current_step = 8
        assert tr.is_complete() is True

    def test_step_8_no_prompt(self):
        tr = ThoughtRecord()
        tr.current_step = 8
        assert tr.get_next_prompt() == ""


# =====================================================================
# 4. 感恩练习
# =====================================================================

class TestGratitudeExercises:

    def test_three_exercises(self):
        assert len(GRATITUDE_EXERCISES) == 3

    def test_exercise_structure(self):
        for key, ex in GRATITUDE_EXERCISES.items():
            assert "name" in ex
            assert "instruction" in ex
            assert "follow_up_prompts" in ex
            assert len(ex["instruction"]) > 0
            assert len(ex["follow_up_prompts"]) > 0

    def test_gratitude_journal_exists(self):
        assert "gratitude_journal" in GRATITUDE_EXERCISES
        ex = GRATITUDE_EXERCISES["gratitude_journal"]
        assert "感恩" in ex["name"]

    def test_mental_subtraction_exists(self):
        assert "mental_subtraction" in GRATITUDE_EXERCISES

    def test_gratitude_letter_exists(self):
        assert "gratitude_letter" in GRATITUDE_EXERCISES
