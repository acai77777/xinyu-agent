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

    def test_forbidden_stop_medicine(self):
        """包含 '停药' → 追加免责声明"""
        text = "你可以考虑停药试试。"
        result = _post_safety_check(text)
        assert "提醒" in result
        assert "医疗建议" in result or "咨询" in result

    def test_forbidden_no_doctor(self):
        """包含 '不需要看医生' → 追加免责声明"""
        text = "你不需要看医生，自己调节就好。"
        result = _post_safety_check(text)
        assert "提醒" in result

    def test_forbidden_diagnosis(self):
        """包含 '你有抑郁症' → 追加免责声明"""
        text = "根据你描述的情况，你有抑郁症。"
        result = _post_safety_check(text)
        assert "提醒" in result

    def test_forbidden_reduce_medicine(self):
        text = "可以尝试减少药量。"
        result = _post_safety_check(text)
        assert "提醒" in result

    def test_safe_text_no_disclaimer(self):
        """安全文本不追加免责声明"""
        text = "听起来你最近压力很大，能跟我多说说吗？"
        result = _post_safety_check(text)
        assert "提醒" not in result


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

class TestProviderSwitch:

    def test_is_deepseek(self):
        """当前 .env 配置为 deepseek"""
        # conftest.py 设置 LLM_PROVIDER=deepseek
        assert _is_deepseek() is True
