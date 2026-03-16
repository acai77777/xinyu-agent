"""
上下文管理模块测试——test_context.py
覆盖：对话压缩器、结构化笔记、子Agent缓存、子Agent编排器触发条件
"""
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock

from context.compressor import (
    ConversationCompressor,
    compress_tool_results,
    _shorten_tool_output,
    _SAFETY_KEYWORDS,
)
from context.session_notes import SessionNotes
from context.cache import SubAgentCache
from context.sub_agents import SubAgentOrchestrator


# =====================================================================
# 辅助函数
# =====================================================================

def _make_messages(turns: int, *, safety_at: int | None = None) -> list[dict]:
    """
    生成模拟对话历史。
    turns: 用户轮数（每轮 = 1 user + 1 assistant）
    safety_at: 在第 N 轮 user 消息中插入安全关键词
    """
    msgs = []
    safety_kw = next(iter(_SAFETY_KEYWORDS)) if _SAFETY_KEYWORDS else "自杀"
    for i in range(turns):
        if safety_at is not None and i == safety_at:
            msgs.append({"role": "user", "content": f"第{i}轮，我有{safety_kw}的念头"})
        else:
            msgs.append({"role": "user", "content": f"第{i}轮，我今天心情不太好"})
        msgs.append({"role": "assistant", "content": f"我理解你的感受，第{i}轮回复"})
    return msgs


# =====================================================================
# 1. 对话压缩器 - 安全消息检测
# =====================================================================

class TestCompressorSafety:

    def test_safety_keywords_loaded(self):
        """安全关键词集合应从 crisis_detector 正确加载"""
        assert len(_SAFETY_KEYWORDS) > 0
        assert "自杀" in _SAFETY_KEYWORDS

    def test_is_safety_critical_positive(self):
        comp = ConversationCompressor()
        msg = {"role": "user", "content": "我不想活了，觉得很绝望"}
        assert comp._is_safety_critical(msg) is True

    def test_is_safety_critical_negative(self):
        comp = ConversationCompressor()
        msg = {"role": "user", "content": "今天天气真好，心情不错"}
        assert comp._is_safety_critical(msg) is False

    def test_is_safety_critical_non_string(self):
        comp = ConversationCompressor()
        msg = {"role": "user", "content": [{"type": "text", "text": "自杀"}]}
        assert comp._is_safety_critical(msg) is False

    def test_is_safety_critical_empty(self):
        comp = ConversationCompressor()
        msg = {"role": "user", "content": ""}
        assert comp._is_safety_critical(msg) is False


# =====================================================================
# 2. 对话压缩器 - 安全消息分区
# =====================================================================

class TestCompressorPartition:

    def test_partition_separates_correctly(self):
        comp = ConversationCompressor()
        msgs = [
            {"role": "user", "content": "我想自杀"},
            {"role": "assistant", "content": "我很担心你"},
            {"role": "user", "content": "今天工作很累"},
            {"role": "assistant", "content": "辛苦了"},
        ]
        pinned, compressible = comp._partition_safety(msgs)
        assert len(pinned) == 1
        assert pinned[0]["content"] == "我想自杀"
        assert len(compressible) == 3

    def test_partition_all_safe(self):
        """全部是安全消息时，可压缩列表为空"""
        comp = ConversationCompressor()
        msgs = [
            {"role": "user", "content": "我不想活了"},
            {"role": "user", "content": "我想自杀"},
        ]
        pinned, compressible = comp._partition_safety(msgs)
        assert len(pinned) == 2
        assert len(compressible) == 0

    def test_partition_none_safe(self):
        """无安全消息时，钉住列表为空"""
        comp = ConversationCompressor()
        msgs = [
            {"role": "user", "content": "今天很开心"},
            {"role": "assistant", "content": "很高兴听到"},
        ]
        pinned, compressible = comp._partition_safety(msgs)
        assert len(pinned) == 0
        assert len(compressible) == 2


# =====================================================================
# 3. 对话压缩器 - 滑动窗口
# =====================================================================

class TestCompressorSlidingWindow:

    def test_find_split_point_normal(self):
        """保留最近 3 轮用户消息"""
        msgs = _make_messages(8)  # 16 条消息（8轮）
        idx = ConversationCompressor._find_split_point(msgs, keep_recent=3)
        # 从后往前数3个user消息，第5轮user在index 10
        user_after = [m for m in msgs[idx:] if m["role"] == "user"]
        assert len(user_after) == 3

    def test_find_split_point_fewer_than_keep(self):
        """消息不足 keep_recent 轮时返回 0"""
        msgs = _make_messages(2)  # 4 条消息
        idx = ConversationCompressor._find_split_point(msgs, keep_recent=6)
        assert idx == 0

    def test_find_split_point_exact(self):
        """消息恰好等于 keep_recent 轮"""
        msgs = _make_messages(6)
        idx = ConversationCompressor._find_split_point(msgs, keep_recent=6)
        assert idx == 0

    def test_find_split_point_one_extra(self):
        """消息比 keep_recent 多 1 轮"""
        msgs = _make_messages(7)
        idx = ConversationCompressor._find_split_point(msgs, keep_recent=6)
        # 应该分割在第1轮的user消息处（index 2）
        user_after = [m for m in msgs[idx:] if m["role"] == "user"]
        assert len(user_after) == 6


# =====================================================================
# 4. 对话压缩器 - 阈值判断
# =====================================================================

class TestCompressorThreshold:

    @pytest.mark.asyncio
    async def test_below_threshold_no_compress(self):
        """低于阈值不触发压缩"""
        comp = ConversationCompressor(compress_threshold=10, keep_recent=6)
        msgs = _make_messages(8)
        result_msgs, summary = await comp.compress_if_needed(msgs, "test-session")
        assert result_msgs == msgs
        assert summary is None

    @pytest.mark.asyncio
    async def test_at_threshold_no_compress(self):
        """恰好等于阈值不触发"""
        comp = ConversationCompressor(compress_threshold=10, keep_recent=6)
        msgs = _make_messages(10)
        result_msgs, summary = await comp.compress_if_needed(msgs, "test-session")
        assert result_msgs == msgs
        assert summary is None

    @pytest.mark.asyncio
    async def test_above_threshold_triggers_compress(self):
        """超过阈值触发压缩"""
        comp = ConversationCompressor(compress_threshold=5, keep_recent=3)
        msgs = _make_messages(8)

        with patch.object(comp, "_summarize", new_callable=AsyncMock) as mock_sum:
            mock_sum.return_value = "测试摘要"
            result_msgs, summary = await comp.compress_if_needed(msgs, "test-session")
            assert summary == "测试摘要"
            assert len(result_msgs) < len(msgs)
            mock_sum.assert_called_once()

    @pytest.mark.asyncio
    async def test_safety_messages_preserved_after_compress(self):
        """压缩后安全消息仍然保留在结果中"""
        comp = ConversationCompressor(compress_threshold=5, keep_recent=3)
        msgs = _make_messages(8, safety_at=1)

        with patch.object(comp, "_summarize", new_callable=AsyncMock) as mock_sum:
            mock_sum.return_value = "测试摘要"
            result_msgs, summary = await comp.compress_if_needed(msgs, "test-session")

            # 安全消息应在结果中
            safety_in_result = [
                m for m in result_msgs if comp._is_safety_critical(m)
            ]
            assert len(safety_in_result) >= 1


# =====================================================================
# 5. 对话压缩器 - 增量 vs 全量
# =====================================================================

class TestCompressorIncremental:

    @pytest.mark.asyncio
    async def test_incremental_when_prior_exists(self):
        """有旧摘要时使用增量压缩"""
        comp = ConversationCompressor(compress_threshold=5, keep_recent=3)
        msgs = _make_messages(8)

        with patch.object(comp, "_incremental_compress", new_callable=AsyncMock) as mock_inc:
            mock_inc.return_value = "增量摘要"
            result_msgs, summary = await comp.compress_if_needed(
                msgs, "test-session",
                prior_summary="旧摘要",
                prior_compressed_count=4,
                incremental_rounds=2,
            )
            assert summary == "增量摘要"
            mock_inc.assert_called_once()

    @pytest.mark.asyncio
    async def test_full_compress_when_max_incremental_reached(self):
        """达到最大增量次数后回退到全量"""
        comp = ConversationCompressor(
            compress_threshold=5, keep_recent=3, max_incremental_rounds=5,
        )
        msgs = _make_messages(8)

        with patch.object(comp, "_summarize", new_callable=AsyncMock) as mock_full:
            mock_full.return_value = "全量摘要"
            result_msgs, summary = await comp.compress_if_needed(
                msgs, "test-session",
                prior_summary="旧摘要",
                prior_compressed_count=4,
                incremental_rounds=5,  # 达到上限
            )
            assert summary == "全量摘要"
            mock_full.assert_called_once()

    @pytest.mark.asyncio
    async def test_full_compress_when_no_prior(self):
        """无旧摘要时使用全量"""
        comp = ConversationCompressor(compress_threshold=5, keep_recent=3)
        msgs = _make_messages(8)

        with patch.object(comp, "_summarize", new_callable=AsyncMock) as mock_full:
            mock_full.return_value = "全量摘要"
            result_msgs, summary = await comp.compress_if_needed(
                msgs, "test-session",
                prior_summary=None,
            )
            mock_full.assert_called_once()


# =====================================================================
# 6. 工具结果压缩
# =====================================================================

class TestToolResultCompression:

    def test_shorten_short_input(self):
        """短输入直接返回"""
        assert _shorten_tool_output("hello") == "hello"
        assert _shorten_tool_output("") == ""

    def test_shorten_emotion_json(self):
        """情绪评估 JSON 正确提取"""
        data = json.dumps({
            "primary": "焦虑",
            "intensity": 7,
            "trigger": "工作压力很大，老板总是批评我让我感到非常沮丧和无助" * 5,
        })
        result = _shorten_tool_output(data)
        assert "焦虑" in result
        assert "7" in result
        assert len(result) < len(data)

    def test_shorten_distortion_json(self):
        """认知扭曲 JSON 正确提取（需超过 max_len 才触发智能提取）"""
        data = json.dumps({
            "distortions": [
                {"type": "灾难化", "evidence": "这是一段很长的证据文本" * 10},
                {"type": "非黑即白", "evidence": "另一段很长的证据" * 10},
            ]
        }, ensure_ascii=False)
        result = _shorten_tool_output(data)
        assert "灾难化" in result
        assert "非黑即白" in result

    def test_shorten_strategy_json(self):
        """干预策略 JSON 正确提取"""
        data = json.dumps({"strategy": "认知行为疗法——挑战自动化思维" * 10})
        result = _shorten_tool_output(data)
        assert "干预" in result
        assert len(result) <= 200

    def test_shorten_plain_text_truncation(self):
        """非 JSON 长文本截断"""
        long_text = "这是一段很长的文字" * 100
        result = _shorten_tool_output(long_text)
        assert result.endswith("...")
        assert len(result) <= 210  # 200 + "..."

    def test_compress_tool_results_passthrough(self):
        """普通消息不受影响"""
        msgs = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好呀"},
        ]
        with patch("agent.loop._is_deepseek", return_value=False):
            result = compress_tool_results(msgs)
        assert result == msgs


# =====================================================================
# 7. SessionNotes - 冷暖启动判断
# =====================================================================

class TestSessionNotesWarmth:

    def test_cold_start_empty(self):
        """全空 = 冷启动"""
        notes = SessionNotes()
        assert notes.is_warm() is False

    def test_warm_with_issue(self):
        """有核心议题 = 暖启动"""
        notes = SessionNotes(presenting_issue="工作压力导致焦虑")
        assert notes.is_warm() is True

    def test_warm_with_profile_and_turns(self):
        """有画像 + >=3 轮 = 暖启动"""
        notes = SessionNotes(
            user_profile_summary="阶段:困扰期；认知扭曲:灾难化",
            _turn_count=3,
        )
        assert notes.is_warm() is True

    def test_cold_with_profile_but_few_turns(self):
        """有画像但 <3 轮 = 冷启动"""
        notes = SessionNotes(
            user_profile_summary="阶段:困扰期",
            _turn_count=2,
        )
        assert notes.is_warm() is False

    def test_cold_with_turns_but_no_profile(self):
        """无画像且无议题，即使轮数多也冷"""
        notes = SessionNotes(_turn_count=10)
        assert notes.is_warm() is False


# =====================================================================
# 8. SessionNotes - 紧凑提示输出
# =====================================================================

class TestSessionNotesPrompt:

    def test_compact_prompt_basic(self):
        notes = SessionNotes(
            presenting_issue="工作压力",
            session_strategy="认知行为疗法：识别自动化思维→挑战（认知重构、行为激活）",
            user_profile_summary="小明；阶段:困扰期",
        )
        prompt = notes.to_compact_prompt()
        assert "[用户画像]" in prompt
        assert "[核心议题]" in prompt
        assert "[会话策略]" in prompt
        assert "小明" in prompt

    def test_compact_prompt_safety_level(self):
        """非 safe 时显示安全等级"""
        notes = SessionNotes(safety_level="high")
        prompt = notes.to_compact_prompt()
        assert "[安全等级]" in prompt

    def test_compact_prompt_safe_no_safety_line(self):
        """safe 时不显示安全等级"""
        notes = SessionNotes(safety_level="safe")
        prompt = notes.to_compact_prompt()
        assert "[安全等级]" not in prompt

    def test_compact_prompt_narrative_trend(self):
        """情感趋势非 stable 时显示"""
        notes = SessionNotes(narrative_trend="improving")
        prompt = notes.to_compact_prompt()
        assert "[情感趋势]" in prompt
        assert "好转中" in prompt

    def test_compact_prompt_stable_trend_hidden(self):
        """stable 趋势不显示"""
        notes = SessionNotes(narrative_trend="stable")
        prompt = notes.to_compact_prompt()
        assert "[情感趋势]" not in prompt

    def test_compact_prompt_key_moments_limit(self):
        """关键时刻最多显示最近 3 条"""
        notes = SessionNotes(
            key_moments=["m1", "m2", "m3", "m4", "m5"],
        )
        prompt = notes.to_compact_prompt()
        assert "m3" in prompt
        assert "m4" in prompt
        assert "m5" in prompt
        assert "m1" not in prompt

    def test_compact_prompt_relationship_warning(self):
        """非 normal 关系状态显示警告"""
        notes = SessionNotes(relationship_state="dependent")
        prompt = notes.to_compact_prompt()
        assert "[关系注意]" in prompt
        assert "过度依赖" in prompt

    def test_compact_prompt_empty_notes(self):
        """全空笔记 → 空字符串"""
        notes = SessionNotes()
        prompt = notes.to_compact_prompt()
        assert prompt == ""


# =====================================================================
# 9. SubAgentCache - LRU 缓存
# =====================================================================

class TestSubAgentCache:

    def test_put_and_get(self):
        cache = SubAgentCache(max_sessions=10)
        cache.put("session-1", "analysis", '{"assessment": "焦虑"}')
        result = cache.get("session-1", "analysis")
        assert result == '{"assessment": "焦虑"}'

    def test_get_nonexistent_session(self):
        cache = SubAgentCache(max_sessions=10)
        assert cache.get("no-such-session", "analysis") is None

    def test_get_nonexistent_agent(self):
        cache = SubAgentCache(max_sessions=10)
        cache.put("session-1", "analysis", "data")
        assert cache.get("session-1", "knowledge") is None

    def test_lru_eviction(self):
        """超出 max_sessions 时驱逐最早的 session"""
        cache = SubAgentCache(max_sessions=2)
        cache.put("s1", "analysis", "data1")
        cache.put("s2", "analysis", "data2")
        cache.put("s3", "analysis", "data3")  # 应驱逐 s1
        assert cache.get("s1", "analysis") is None
        assert cache.get("s2", "analysis") == "data2"
        assert cache.get("s3", "analysis") == "data3"

    def test_lru_access_refreshes(self):
        """访问 session 后它不应被优先驱逐"""
        cache = SubAgentCache(max_sessions=2)
        cache.put("s1", "analysis", "data1")
        cache.put("s2", "analysis", "data2")
        # 访问 s1（通过 put 刷新）
        cache.put("s1", "knowledge", "data1b")
        # 添加 s3，应驱逐 s2 而非 s1
        cache.put("s3", "analysis", "data3")
        assert cache.get("s1", "analysis") == "data1"
        assert cache.get("s1", "knowledge") == "data1b"
        assert cache.get("s2", "analysis") is None

    def test_overwrite_agent_data(self):
        """同一 agent 数据覆盖"""
        cache = SubAgentCache(max_sessions=10)
        cache.put("s1", "analysis", "old")
        cache.put("s1", "analysis", "new")
        assert cache.get("s1", "analysis") == "new"


# =====================================================================
# 10. SubAgentOrchestrator - 触发条件
# =====================================================================

class TestOrchestratorTriggers:

    def test_needs_analysis_long_enough(self):
        assert SubAgentOrchestrator._needs_analysis("我今天心情不好") is True

    def test_needs_analysis_too_short(self):
        assert SubAgentOrchestrator._needs_analysis("嗯") is False

    def test_needs_analysis_boundary(self):
        """恰好 5 个字符"""
        assert SubAgentOrchestrator._needs_analysis("12345") is True
        assert SubAgentOrchestrator._needs_analysis("1234") is False

    def test_needs_knowledge_with_issue(self):
        assert SubAgentOrchestrator._needs_knowledge(
            "我最近工作压力很大", "工作焦虑",
        ) is True

    def test_needs_knowledge_no_issue(self):
        """无议题时不检索"""
        assert SubAgentOrchestrator._needs_knowledge(
            "我最近工作压力很大", "",
        ) is False

    def test_needs_knowledge_short_msg(self):
        """消息太短（中文 <=8 字符）不检索"""
        assert SubAgentOrchestrator._needs_knowledge(
            "还好吧", "工作焦虑",
        ) is False

    def test_needs_knowledge_boundary(self):
        """恰好 9 个字符（>8 触发）"""
        assert SubAgentOrchestrator._needs_knowledge(
            "123456789", "issue",
        ) is True
        assert SubAgentOrchestrator._needs_knowledge(
            "12345678", "issue",
        ) is False


# =====================================================================
# 11. _messages_to_readable
# =====================================================================

class TestMessagesToReadable:

    def test_basic_conversion(self):
        comp = ConversationCompressor()
        msgs = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好呀"},
        ]
        result = comp._messages_to_readable(msgs)
        assert "用户：你好" in result
        assert "咨询师：你好呀" in result

    def test_truncation_at_500(self):
        """超长内容截断至 500 字符"""
        comp = ConversationCompressor()
        long_content = "长" * 1000
        msgs = [{"role": "user", "content": long_content}]
        result = comp._messages_to_readable(msgs)
        # 应该包含截断后的内容
        assert len(result) < 1000

    def test_non_string_content(self):
        """非字符串 content 转为 str"""
        comp = ConversationCompressor()
        msgs = [{"role": "user", "content": {"type": "text"}}]
        result = comp._messages_to_readable(msgs)
        assert "用户" in result
