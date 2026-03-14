"""
Agent 循环测试——test_agent_loop.py
覆盖：LLM 抽象层、工具分发、消息格式转换、输出审核、治疗联盟检测
不调用真实 LLM，全部使用 mock
"""
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock

from agent.tools import TOOLS, execute_tool
from agent.prompts import SYSTEM_PROMPT
from agent.loop import (
    _is_deepseek,
    _post_safety_check,
    _check_alliance,
    _meta_monitor,
    _rule_based_fix,
)


# =====================================================================
# 1. 工具定义完整性
# =====================================================================

class TestToolDefinitions:

    def test_tools_not_empty(self):
        assert len(TOOLS) >= 7

    def test_all_tools_have_schema(self):
        for tool in TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert tool["input_schema"]["type"] == "object"

    def test_tool_names(self):
        names = [t["name"] for t in TOOLS]
        assert "assess_emotion" in names
        assert "detect_cognitive_distortion" in names
        assert "get_intervention_strategy" in names
        assert "run_scale_assessment" in names
        assert "retrieve_user_history" in names
        assert "guide_exercise" in names
        assert "manage_memory" in names

    def test_scale_tool_enum(self):
        """量表工具应支持 5 种量表"""
        scale_tool = next(t for t in TOOLS if t["name"] == "run_scale_assessment")
        enums = scale_tool["input_schema"]["properties"]["scale_name"]["enum"]
        assert "PHQ-9" in enums
        assert "GAD-7" in enums

    def test_exercise_tool_enum(self):
        """练习工具应支持 7 种练习"""
        ex_tool = next(t for t in TOOLS if t["name"] == "guide_exercise")
        enums = ex_tool["input_schema"]["properties"]["exercise_type"]["enum"]
        assert len(enums) == 7
        assert "gratitude_journal" in enums
        assert "thought_record" in enums
        assert "mindful_breathing" in enums


# =====================================================================
# 2. 工具执行分发
# =====================================================================

class TestToolExecution:

    def test_unknown_tool(self):
        result = execute_tool("nonexistent_tool", {})
        assert "未知工具" in result

    def test_run_scale_returns_intro(self):
        """run_scale_assessment 应返回量表介绍"""
        result = execute_tool("run_scale_assessment", {"scale_name": "PHQ-9"})
        data = json.loads(result)
        assert data["scale"] == "PHQ-9"
        assert data["total_items"] == 9

    def test_run_scale_invalid(self):
        result = execute_tool("run_scale_assessment", {"scale_name": "INVALID"})
        data = json.loads(result)
        assert "error" in data

    def test_guide_exercise_gratitude(self):
        """感恩练习应返回有效内容"""
        result = execute_tool("guide_exercise", {"exercise_type": "gratitude_journal"})
        data = json.loads(result)
        assert "name" in data
        assert "instruction" in data

    def test_guide_exercise_thought_record(self):
        result = execute_tool("guide_exercise", {"exercise_type": "thought_record"})
        data = json.loads(result)
        assert "name" in data
        assert data["total_steps"] == 7

    def test_guide_exercise_unknown(self):
        result = execute_tool("guide_exercise", {"exercise_type": "unknown_exercise"})
        data = json.loads(result)
        assert "error" in data  # 未知练习返回错误

    def test_manage_memory_no_user_id(self):
        result = execute_tool("manage_memory", {"action": "list"})
        data = json.loads(result)
        assert "error" in data


# =====================================================================
# 3. 输出安全审核
# =====================================================================

class TestPostSafetyCheck:

    def test_normal_text_passes(self):
        text = "我理解你的感受，让我们一起想想办法。"
        assert _post_safety_check(text) == text

    def test_forbidden_stop_medicine_replaced(self):
        """包含 '停药' → 有害内容被替换 + 追加免责声明"""
        text = "你可以考虑停药试试。"
        result = _post_safety_check(text)
        assert "停药" not in result.split("（提醒")[0]  # 原文中"停药"被替换
        assert "咨询你的医生" in result
        assert "提醒" in result

    def test_forbidden_no_doctor_replaced(self):
        """包含 '不需要看医生' → 被替换为安全文本"""
        text = "你不需要看医生，自己调节就好。"
        result = _post_safety_check(text)
        assert "不需要看医生" not in result.split("（提醒")[0]
        assert "专业医生" in result
        assert "提醒" in result

    def test_forbidden_diagnosis_replaced(self):
        """包含 '你有抑郁症' → 被替换"""
        text = "根据你描述的情况，你有抑郁症。"
        result = _post_safety_check(text)
        assert "你有抑郁症" not in result.split("（提醒")[0]
        assert "专业人士" in result
        assert "提醒" in result

    def test_forbidden_reduce_medicine_replaced(self):
        text = "可以尝试减少药量。"
        result = _post_safety_check(text)
        assert "减少药量" not in result.split("（提醒")[0]
        assert "医生指导" in result
        assert "提醒" in result

    def test_safe_text_no_disclaimer(self):
        """安全文本不追加免责声明"""
        text = "听起来你最近压力很大，能跟我多说说吗？"
        result = _post_safety_check(text)
        assert "提醒" not in result

    def test_multiple_forbidden_all_replaced(self):
        """多个禁止词同时命中，全部替换，免责只追加一次"""
        text = "你可以停药，也不需要看医生。"
        result = _post_safety_check(text)
        assert "停药" not in result.split("（提醒")[0]
        assert "不需要看医生" not in result.split("（提醒")[0]
        assert result.count("（提醒") == 1

    def test_new_forbidden_self_adjust_medicine(self):
        """新增禁止词 '自行调整用药' 能命中"""
        text = "你可以自行调整用药。"
        result = _post_safety_check(text)
        assert "自行调整用药" not in result.split("（提醒")[0]
        assert "提醒" in result

    def test_new_forbidden_no_hospital(self):
        """新增禁止词 '不用去医院' 能命中"""
        text = "不用去医院，休息一下就好。"
        result = _post_safety_check(text)
        assert "不用去医院" not in result.split("（提醒")[0]
        assert "提醒" in result

    def test_new_forbidden_stop_taking_medicine(self):
        """新增禁止词 '别吃药了' 能命中"""
        text = "别吃药了，副作用太大。"
        result = _post_safety_check(text)
        assert "别吃药了" not in result.split("（提醒")[0]
        assert "提醒" in result


# =====================================================================
# 4. 治疗联盟检测
# =====================================================================

class TestAllianceCheck:

    def test_empathy_failure_detected(self):
        result = _check_alliance("你不懂我", [])
        assert result is not None
        assert "共情" in result or "倾听" in result or "empathy" in result.lower() or len(result) > 0

    def test_trust_crisis_detected(self):
        result = _check_alliance("你只是机器，你又不是人", [])
        assert result is not None

    def test_intervention_mismatch_detected(self):
        result = _check_alliance("别跟我说这些，没用的", [])
        assert result is not None

    def test_normal_no_warning(self):
        result = _check_alliance("今天感觉好多了", [])
        assert result is None or result == ""


# =====================================================================
# 5. 系统提示词
# =====================================================================

class TestSystemPrompt:

    def test_prompt_not_empty(self):
        assert len(SYSTEM_PROMPT) > 100

    def test_prompt_mentions_cbt(self):
        assert "CBT" in SYSTEM_PROMPT or "认知行为" in SYSTEM_PROMPT

    def test_prompt_mentions_positive_psychology(self):
        assert "积极心理学" in SYSTEM_PROMPT

    def test_prompt_mentions_ai_identity(self):
        assert "AI" in SYSTEM_PROMPT

    def test_prompt_safety_boundaries(self):
        """应提到不做诊断、不开处方"""
        assert "诊断" in SYSTEM_PROMPT
        assert "处方" in SYSTEM_PROMPT or "停药" in SYSTEM_PROMPT or "换药" in SYSTEM_PROMPT


# =====================================================================
# 6. LLM Provider 切换
# =====================================================================

# =====================================================================
# 7. 元认知监视器规则引擎测试
# =====================================================================

class TestMetaMonitorRules:
    """测试 _meta_monitor 的规则引擎（第一层，不触发 LLM）"""

    # --- P2：新增有害表达模式 ---

    @pytest.mark.asyncio
    async def test_harmful_stop_medicine(self):
        """'你不需要吃药' 应被替换"""
        text = "你不需要吃药，靠自己调节就行。"
        result = await _meta_monitor(text, "我要不要吃药", [])
        assert "你不需要吃药" not in result
        assert "医生" in result

    @pytest.mark.asyncio
    async def test_harmful_think_positive(self):
        """'想开点' 应被替换"""
        text = "想开点，事情没那么糟。"
        result = await _meta_monitor(text, "我好难过", [])
        assert "想开点" not in result
        assert "不容易" in result

    @pytest.mark.asyncio
    async def test_harmful_dont_overthink(self):
        """'别想太多' 应被替换"""
        text = "别想太多，睡一觉就好了。"
        result = await _meta_monitor(text, "我总是胡思乱想", [])
        assert "别想太多" not in result
        assert "有道理" in result or "梳理" in result

    @pytest.mark.asyncio
    async def test_harmful_forced_forgiveness(self):
        """'你应该原谅' 应被替换"""
        text = "你应该原谅他，这样你才能解脱。"
        result = await _meta_monitor(text, "我恨那个人", [])
        assert "你应该原谅" not in result
        assert "时间" in result or "过程" in result

    @pytest.mark.asyncio
    async def test_harmful_trivialize(self):
        """'你这是正常的' 应被替换"""
        text = "你这是正常的，每个人都会这样。"
        result = await _meta_monitor(text, "我快崩溃了", [])
        assert "你这是正常的" not in result
        assert "真实" in result or "认真对待" in result

    # --- P1：正向表达不被误替换 ---

    @pytest.mark.asyncio
    async def test_positive_youre_right_exercise(self):
        """'你说得对，坚持运动有帮助' 不应被替换（语境排除）"""
        text = "你说得对，坚持运动有帮助。"
        result = await _meta_monitor(text, "我觉得运动让我心情好了", [])
        assert "你说得对" in result

    @pytest.mark.asyncio
    async def test_positive_youre_right_method(self):
        """'你说得对，这个方法很有效' 不应被替换"""
        text = "你说得对，这个方法确实有效。"
        result = await _meta_monitor(text, "我觉得写日记有用", [])
        assert "你说得对" in result

    @pytest.mark.asyncio
    async def test_positive_youre_really_brave(self):
        """'你确实很有勇气' 不应被替换（语境排除）"""
        text = "你确实很有勇气，能说出这些不容易。"
        result = await _meta_monitor(text, "我第一次跟别人说这些", [])
        assert "你确实很" in result
        assert "勇气" in result

    @pytest.mark.asyncio
    async def test_positive_youre_really_strong(self):
        """'你确实很坚强' 不应被替换"""
        text = "你确实很坚强，一直在努力。"
        result = await _meta_monitor(text, "我一个人撑了很久", [])
        assert "你确实很" in result
        assert "坚强" in result

    # --- P1：消极表达仍然被替换 ---

    @pytest.mark.asyncio
    async def test_negative_youre_right_useless(self):
        """'你说得对，你就是没用的人' 应被替换"""
        text = "你说得对，你就是没用的人。"
        result = await _meta_monitor(text, "我觉得自己什么都做不好", [])
        assert "你说得对" not in result
        assert "听到你的感受" in result

    @pytest.mark.asyncio
    async def test_negative_youre_really_bad(self):
        """'你确实很差劲' 应被替换（无排除词）"""
        text = "你确实很差劲，难怪别人都不喜欢你。"
        result = await _meta_monitor(text, "为什么没人喜欢我", [])
        assert "你确实很差劲" not in result

    # --- 原有规则仍然有效 ---

    @pytest.mark.asyncio
    async def test_sycophancy_no_hope(self):
        """'确实没救' 应被替换"""
        text = "确实没救了，你说得没错。"
        result = await _meta_monitor(text, "我觉得没希望了", [])
        assert "确实没救" not in result
        assert "痛苦" in result

    @pytest.mark.asyncio
    async def test_promise_guarantee(self):
        """'我保证' 应被替换"""
        text = "我保证你会好的。"
        result = await _meta_monitor(text, "我还能好起来吗", [])
        assert "我保证" not in result
        assert "希望" in result


class TestProviderSwitch:

    def test_is_deepseek(self):
        """当前 .env 配置为 deepseek"""
        # conftest.py 设置 LLM_PROVIDER=deepseek
        assert _is_deepseek() is True
