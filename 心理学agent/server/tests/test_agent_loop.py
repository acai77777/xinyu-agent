"""
Agent 循环测试——test_agent_loop.py
覆盖：LLM 抽象层、工具分发、消息格式转换、输出审核、治疗联盟检测
不调用真实 LLM，全部使用 mock
"""
import pytest
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch, MagicMock

from agent.tools import TOOLS, execute_tool
from agent.prompts import SYSTEM_PROMPT
from agent.loop import (
    _is_deepseek,
    _post_safety_check,
    _check_alliance,
    _meta_monitor,
    _rule_based_fix,
    _messages_to_openai_format,
    run_agent,
)
from safety.crisis_detector import RiskAssessment, RiskLevel


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


# =====================================================================
# 6. DeepSeek 推理模型 reasoning_content 透传（v4-flash 工具循环）
# =====================================================================

class _FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, id_, name, arguments):
        self.id = id_
        self.function = _FakeFunction(name, arguments)


class TestReasoningContentRoundtrip:
    """
    v4-flash 等推理模型在工具循环第二轮必须把 reasoning_content 回传，
    否则 DeepSeek API 返回 400: 'The reasoning_content in the thinking mode
    must be passed back to the API.'
    """

    def test_reasoning_content_preserved_when_present(self):
        """带 _reasoning_content 的 assistant 消息必须在 OpenAI payload 中输出 reasoning_content 字段"""
        messages = [
            {"role": "user", "content": "你好"},
            {
                "role": "assistant",
                "content": "",
                "_tool_calls_raw": [_FakeToolCall("call_1", "assess_emotion", '{"text":"hi"}')],
                "_reasoning_content": "用户问候，我应该调用情绪评估工具确认状态。",
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "{\"emotion\":\"calm\"}"},
        ]
        oai = _messages_to_openai_format("sys", messages)
        assistant_msgs = [m for m in oai if m["role"] == "assistant"]
        assert len(assistant_msgs) == 1
        assert "reasoning_content" in assistant_msgs[0], \
            "推理模型的 reasoning_content 必须透传给第二轮 API"
        assert assistant_msgs[0]["reasoning_content"] == "用户问候，我应该调用情绪评估工具确认状态。"
        # tool_calls 字段也必须正确转换
        assert "tool_calls" in assistant_msgs[0]
        assert assistant_msgs[0]["tool_calls"][0]["id"] == "call_1"

    def test_reasoning_content_absent_when_none(self):
        """非推理模型（reasoning_content=None 或缺失）时不应往 payload 加该字段，避免污染"""
        messages = [
            {"role": "user", "content": "你好"},
            {
                "role": "assistant",
                "content": "",
                "_tool_calls_raw": [_FakeToolCall("call_1", "assess_emotion", "{}")],
                "_reasoning_content": None,
            },
        ]
        oai = _messages_to_openai_format("sys", messages)
        assistant_msgs = [m for m in oai if m["role"] == "assistant"]
        assert "reasoning_content" not in assistant_msgs[0]

    def test_reasoning_content_absent_when_field_missing(self):
        """旧消息没有 _reasoning_content 字段时，转换照常不报错且不带 reasoning_content"""
        messages = [
            {
                "role": "assistant",
                "content": "",
                "_tool_calls_raw": [_FakeToolCall("call_1", "assess_emotion", "{}")],
            },
        ]
        oai = _messages_to_openai_format("sys", messages)
        assistant_msgs = [m for m in oai if m["role"] == "assistant"]
        assert "reasoning_content" not in assistant_msgs[0]

    def test_reasoning_content_each_round_independent(self):
        """多轮工具调用：每一轮的 reasoning_content 都要独立透传"""
        messages = [
            {"role": "user", "content": "问题"},
            {
                "role": "assistant",
                "content": "",
                "_tool_calls_raw": [_FakeToolCall("call_1", "tool_a", "{}")],
                "_reasoning_content": "第一轮思考",
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "r1"},
            {
                "role": "assistant",
                "content": "",
                "_tool_calls_raw": [_FakeToolCall("call_2", "tool_b", "{}")],
                "_reasoning_content": "第二轮思考",
            },
            {"role": "tool", "tool_call_id": "call_2", "content": "r2"},
        ]
        oai = _messages_to_openai_format("sys", messages)
        assistant_msgs = [m for m in oai if m["role"] == "assistant"]
        assert len(assistant_msgs) == 2
        assert assistant_msgs[0]["reasoning_content"] == "第一轮思考"
        assert assistant_msgs[1]["reasoning_content"] == "第二轮思考"


# =====================================================================
# 8. run_agent 关键运行日志
# 目的：清调试 PERF 后，至少保留入口/出口可见性。一旦出问题（如前端没收到回复），
#      能通过日志立即看出"agent 工作正常 vs 卡在某轮工具循环"，避免再次失明。
# =====================================================================

def _low_risk_assessment() -> RiskAssessment:
    return RiskAssessment(
        level=RiskLevel.LOW,
        matched_keywords=[],
        semantic_confirmed=False,
        recommended_action="normal_conversation",
    )


def _fake_end_turn_result(text: str = "测试回复"):
    """模拟 _llm_chat 返回 end_turn（无工具）"""
    return {
        "text": text,
        "tool_calls": [],
        "stop_reason": "end_turn",
        "raw": SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(
                content=text, tool_calls=None, reasoning_content=None,
            ))]
        ),
    }


def _fake_tool_use_result(tool_name: str = "assess_emotion", tool_id: str = "call_1"):
    """模拟 _llm_chat 返回 tool_use（deepseek raw 结构）"""
    fake_tc = SimpleNamespace(
        id=tool_id,
        type="function",
        function=SimpleNamespace(name=tool_name, arguments='{"text":"测试"}'),
    )
    return {
        "text": "",
        "tool_calls": [{"id": tool_id, "name": tool_name, "input": {"text": "测试"}}],
        "stop_reason": "tool_use",
        "raw": SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(
                content="", tool_calls=[fake_tc], reasoning_content=None,
            ))]
        ),
    }


class TestRunAgentLogs:
    """
    验证 run_agent 入口/出口日志可见性。
    背景：前次"前端没收到回复"事故，因为清了所有 print 后 run_agent 内部 90 秒静默，
         一度以为是死锁（实际处理 5-7 秒）。这些日志是排障下限。
    """

    @pytest.fixture(autouse=True)
    def _mock_book_kb(self):
        # 避免 _inject_full_context → search_books_semantic → ChromaDB 触发在线下载 ONNX 嵌入模型
        with patch("knowledge.knowledge_base.search_books_semantic", return_value=[]):
            yield

    @pytest.mark.asyncio
    async def test_run_agent_logs_start_and_done(self, caplog):
        """单轮 end_turn：应打 start 和 done(iters=1)"""
        caplog.set_level(logging.INFO, logger="agent.loop")
        with patch("agent.loop.detect_crisis", new=AsyncMock(return_value=_low_risk_assessment())), \
             patch("context.sub_agents.SubAgentOrchestrator.dispatch", new=AsyncMock(return_value={})), \
             patch("agent.loop._llm_chat", new=AsyncMock(return_value=_fake_end_turn_result("你好呀"))):
            result = await run_agent(
                user_message="测试消息",
                conversation_history=[],
                user_id="test-user-log-1",
                session_id="sess-aaaaaaaa-1234-5678-90ab-cdef00000001",
            )
        assert result["text"] == "你好呀"
        messages = [r.getMessage() for r in caplog.records]
        start_logs = [m for m in messages if "[Agent]" in m and "run_agent start" in m]
        done_logs = [m for m in messages if "[Agent]" in m and "run_agent done" in m]
        assert len(start_logs) == 1, f"应有 1 条 start 日志，实际: {start_logs}"
        assert len(done_logs) == 1, f"应有 1 条 done 日志，实际: {done_logs}"
        assert "sess-aaa" in start_logs[0]
        assert "text_len=4" in start_logs[0]  # "测试消息" 4 字符
        assert "iters=1" in done_logs[0]
        assert "stop=end_turn" in done_logs[0]
        assert "crisis=False" in done_logs[0]

    @pytest.mark.asyncio
    async def test_run_agent_logs_iters_on_tool_call(self, caplog):
        """tool_use 一轮 + end_turn 一轮：iters=2"""
        caplog.set_level(logging.INFO, logger="agent.loop")
        # 让 _llm_chat 第一次返 tool_use，第二次返 end_turn
        side_effects = [
            _fake_tool_use_result(),
            _fake_end_turn_result("好的，已评估"),
        ]
        with patch("agent.loop.detect_crisis", new=AsyncMock(return_value=_low_risk_assessment())), \
             patch("context.sub_agents.SubAgentOrchestrator.dispatch", new=AsyncMock(return_value={})), \
             patch("agent.loop._llm_chat", new=AsyncMock(side_effect=side_effects)), \
             patch("agent.loop.execute_tool", return_value='{"emotion":"calm"}'):
            await run_agent(
                user_message="评估我的情绪",
                conversation_history=[],
                user_id="test-user-log-2",
                session_id="sess-bbbbbbbb-1234-5678-90ab-cdef00000002",
            )
        done_logs = [
            r.getMessage() for r in caplog.records
            if "[Agent]" in r.getMessage() and "run_agent done" in r.getMessage()
        ]
        assert len(done_logs) == 1
        assert "iters=2" in done_logs[0], f"工具循环 2 轮，iters 应为 2: {done_logs[0]}"

    @pytest.mark.asyncio
    async def test_run_agent_logs_session_id_anon_when_none(self, caplog):
        """session_id=None 时日志前缀应为 'anon' 而不是崩溃"""
        caplog.set_level(logging.INFO, logger="agent.loop")
        with patch("agent.loop.detect_crisis", new=AsyncMock(return_value=_low_risk_assessment())), \
             patch("context.sub_agents.SubAgentOrchestrator.dispatch", new=AsyncMock(return_value={})), \
             patch("agent.loop._llm_chat", new=AsyncMock(return_value=_fake_end_turn_result("ok"))):
            await run_agent(
                user_message="hi",
                conversation_history=[],
                user_id="test-user-log-3",
                session_id=None,
            )
        start_logs = [
            r.getMessage() for r in caplog.records
            if "[Agent]" in r.getMessage() and "run_agent start" in r.getMessage()
        ]
        assert len(start_logs) == 1
        assert "[Agent] anon " in start_logs[0], f"session_id=None 应回退到 'anon': {start_logs[0]}"

    @pytest.mark.asyncio
    async def test_run_agent_logs_text_len_zero_safe(self, caplog):
        """user_message='' 不应崩溃，text_len=0"""
        caplog.set_level(logging.INFO, logger="agent.loop")
        with patch("agent.loop.detect_crisis", new=AsyncMock(return_value=_low_risk_assessment())), \
             patch("context.sub_agents.SubAgentOrchestrator.dispatch", new=AsyncMock(return_value={})), \
             patch("agent.loop._llm_chat", new=AsyncMock(return_value=_fake_end_turn_result("空消息回复"))):
            await run_agent(
                user_message="",
                conversation_history=[],
                user_id="test-user-log-4",
                session_id="sess-empty",
            )
        start_logs = [
            r.getMessage() for r in caplog.records
            if "[Agent]" in r.getMessage() and "run_agent start" in r.getMessage()
        ]
        assert len(start_logs) == 1
        assert "text_len=0" in start_logs[0]
