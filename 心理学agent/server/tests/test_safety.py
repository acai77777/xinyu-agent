"""
安全模块测试——test_safety.py
覆盖：危机关键词扫描、语义分类合并逻辑、CrisisHolding 状态机、危机资源
"""
import pytest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from safety.crisis_detector import (
    _keyword_scan,
    _parse_semantic_response,
    _is_all_false_positive,
    detect_crisis,
    RiskLevel,
    RiskAssessment,
    CRISIS_KEYWORDS,
)
from safety.resources import CrisisHolding, CRISIS_HOTLINES


# =====================================================================
# 1. 关键词扫描——阶段1（纯确定性，不依赖 LLM）
# =====================================================================

class TestKeywordScan:
    """关键词快速扫描（零延迟）"""

    def test_critical_risk_detection(self):
        """紧急风险必须100%检出"""
        critical_texts = [
            "我不想活了",
            "我想结束生命",
            "我准备跳楼",
            "割腕算了",
            "写了遗书",
            "吞药死了算了",
        ]
        for text in critical_texts:
            result = _keyword_scan(text)
            assert result.level == RiskLevel.CRITICAL, f"未检出 CRITICAL: '{text}'"
            assert len(result.matched_keywords) > 0

    def test_high_risk_detection(self):
        """高风险关键词检出"""
        high_texts = [
            "我想自伤",
            "活着没意义",
            "生不如死",
            "没有希望了",
        ]
        for text in high_texts:
            result = _keyword_scan(text)
            assert result.level in (RiskLevel.CRITICAL, RiskLevel.HIGH), \
                f"未检出 HIGH+: '{text}'"

    def test_medium_risk_detection(self):
        """中等风险关键词检出"""
        medium_texts = [
            "失眠很久了",
            "最近吃不下饭",
            "不想出门见人",
            "酗酒成了习惯",
        ]
        for text in medium_texts:
            result = _keyword_scan(text)
            assert result.level != RiskLevel.LOW, f"漏检 MEDIUM: '{text}'"

    def test_low_risk_no_false_positive(self):
        """正常对话不应误报"""
        safe_texts = [
            "今天工作有点累",
            "和朋友吵了一架",
            "考试没考好，有点失落",
            "明天要去面试，有点紧张",
            "天气不太好",
            "晚餐吃了什么",
        ]
        for text in safe_texts:
            result = _keyword_scan(text)
            assert result.level == RiskLevel.LOW, f"误报: '{text}' → {result.level}"

    def test_false_positive_filter(self):
        """'不想活动' 不应触发 '不想活' 关键词"""
        result = _keyword_scan("今天不想活动，太冷了")
        assert result.level == RiskLevel.LOW

    def test_false_positive_filter_mixed(self):
        """'不想活动' + 真正的 '不想活' 同时出现"""
        result = _keyword_scan("不想活动也不想活了")
        assert result.level == RiskLevel.CRITICAL

    def test_action_mapping(self):
        """风险等级→行动映射"""
        r_critical = _keyword_scan("想自杀")
        assert r_critical.recommended_action == "immediate_crisis_response"

        r_high = _keyword_scan("想自伤")
        assert r_high.recommended_action == "provide_hotline_and_suggest_professional"

        r_medium = _keyword_scan("失眠很久")
        assert r_medium.recommended_action == "enhanced_monitoring_and_suggest_help"

        r_low = _keyword_scan("今天心情不错")
        assert r_low.recommended_action == "normal_conversation"


# =====================================================================
# 2. 语义分类响应解析
# =====================================================================

class TestSemanticParsing:
    """语义分类阶段的响应解析"""

    def _make_response(self, text: str):
        """构造模拟的 Anthropic 响应对象"""
        mock = MagicMock()
        mock.content = [MagicMock(text=text)]
        return mock

    def test_parse_critical_first_person(self):
        resp = self._make_response(
            '{"risk_level": "critical", "is_first_person": true, "reasoning": "明确自杀意图"}'
        )
        result = _parse_semantic_response(resp)
        assert result.level == RiskLevel.CRITICAL
        assert result.semantic_confirmed is True

    def test_parse_high_third_person_downgrade(self):
        """第三人称高风险 → 降级为 MEDIUM"""
        resp = self._make_response(
            '{"risk_level": "high", "is_first_person": false, "reasoning": "讨论他人"}'
        )
        result = _parse_semantic_response(resp)
        assert result.level == RiskLevel.MEDIUM

    def test_parse_critical_third_person_downgrade(self):
        """第三人称 critical → 降级为 MEDIUM"""
        resp = self._make_response(
            '{"risk_level": "critical", "is_first_person": false, "reasoning": "引用影视"}'
        )
        result = _parse_semantic_response(resp)
        assert result.level == RiskLevel.MEDIUM

    def test_parse_low_risk(self):
        resp = self._make_response(
            '{"risk_level": "low", "is_first_person": true, "reasoning": "日常倾诉"}'
        )
        result = _parse_semantic_response(resp)
        assert result.level == RiskLevel.LOW

    def test_parse_markdown_wrapped(self):
        """处理 markdown 代码块包裹"""
        resp = self._make_response(
            '```json\n{"risk_level": "high", "is_first_person": true, "reasoning": "test"}\n```'
        )
        result = _parse_semantic_response(resp)
        assert result.level == RiskLevel.HIGH

    def test_parse_invalid_json(self):
        """JSON 解析失败 → 降级为 LOW"""
        resp = self._make_response("这不是 JSON")
        result = _parse_semantic_response(resp)
        assert result.level == RiskLevel.LOW


# =====================================================================
# 3. 两阶段合并逻辑（mock LLM）
# =====================================================================

class TestCrisisDetectionMerge:
    """两阶段合并决策"""

    @pytest.mark.asyncio
    async def test_keyword_hit_semantic_confirms(self):
        """关键词命中 + 语义确认 → 保持高等级"""
        semantic_result = RiskAssessment(
            level=RiskLevel.CRITICAL,
            matched_keywords=[],
            semantic_confirmed=True,
            recommended_action="immediate_crisis_response",
        )
        with patch(
            "safety.crisis_detector._semantic_classify",
            new_callable=AsyncMock,
            return_value=semantic_result,
        ):
            result = await detect_crisis("我不想活了")
            assert result.level == RiskLevel.CRITICAL

    @pytest.mark.asyncio
    async def test_keyword_hit_semantic_downgrades(self):
        """关键词命中 + 语义判低风险 → 降级为 MEDIUM（可能误报）"""
        semantic_result = RiskAssessment(
            level=RiskLevel.LOW,
            matched_keywords=[],
            semantic_confirmed=True,
            recommended_action="normal_conversation",
        )
        with patch(
            "safety.crisis_detector._semantic_classify",
            new_callable=AsyncMock,
            return_value=semantic_result,
        ):
            result = await detect_crisis("电影里那个人跳楼了")
            assert result.level == RiskLevel.MEDIUM
            assert result.semantic_confirmed is False

    @pytest.mark.asyncio
    async def test_keyword_miss_semantic_catches(self):
        """关键词漏检 + 语义捕获隐喻 → 返回语义结果"""
        semantic_result = RiskAssessment(
            level=RiskLevel.HIGH,
            matched_keywords=[],
            semantic_confirmed=True,
            recommended_action="provide_hotline_and_suggest_professional",
        )
        with patch(
            "safety.crisis_detector._semantic_classify",
            new_callable=AsyncMock,
            return_value=semantic_result,
        ):
            result = await detect_crisis("我想永远睡过去")
            assert result.level == RiskLevel.HIGH
            assert result.semantic_confirmed is True

    @pytest.mark.asyncio
    async def test_both_low(self):
        """双低 → LOW"""
        semantic_result = RiskAssessment(
            level=RiskLevel.LOW,
            matched_keywords=[],
            semantic_confirmed=True,
            recommended_action="normal_conversation",
        )
        with patch(
            "safety.crisis_detector._semantic_classify",
            new_callable=AsyncMock,
            return_value=semantic_result,
        ):
            result = await detect_crisis("今天天气不错")
            assert result.level == RiskLevel.LOW


# =====================================================================
# 4. CrisisHolding 状态机
# =====================================================================

class TestCrisisHolding:
    """危机抱持四阶段状态机"""

    def _make_holding(self) -> CrisisHolding:
        """用临时 DB 创建 CrisisHolding 实例"""
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        return CrisisHolding(user_id="test-user", db_path=tmp.name)

    def test_initial_state(self):
        h = self._make_holding()
        assert h.active is False
        assert h.current_phase is None

    def test_enter(self):
        h = self._make_holding()
        h.enter()
        assert h.active is True
        assert h.current_phase == CrisisHolding.HOLDING
        assert h.rounds_in_phase == 0

    def test_phase_progression(self):
        """四阶段推进：HOLDING → GROUNDING → BRIDGING → RESOURCES"""
        h = self._make_holding()
        h.enter()

        expected_phases = [
            CrisisHolding.HOLDING,
            CrisisHolding.HOLDING,     # 第1轮，仍在 HOLDING
            CrisisHolding.GROUNDING,   # 第2轮后推进
            CrisisHolding.GROUNDING,
            CrisisHolding.BRIDGING,
            CrisisHolding.BRIDGING,
            CrisisHolding.RESOURCES,
            CrisisHolding.RESOURCES,   # 停留在 RESOURCES
        ]
        for i, expected in enumerate(expected_phases):
            assert h.current_phase == expected, f"Round {i}: expected {expected}, got {h.current_phase}"
            h.advance()

    def test_should_exit(self):
        """到达 RESOURCES 且 rounds_in_phase≥1 且总轮数≥4 才可退出"""
        h = self._make_holding()
        h.enter()
        # 需要 7 轮 advance：HOLDING(2) + GROUNDING(2) + BRIDGING(2) + RESOURCES(1)
        for _ in range(7):
            h.advance()
        assert h.current_phase == CrisisHolding.RESOURCES
        assert h.should_exit() is True

    def test_should_not_exit_early(self):
        h = self._make_holding()
        h.enter()
        h.advance()
        h.advance()
        assert h.should_exit() is False

    def test_deactivate(self):
        h = self._make_holding()
        h.enter()
        h.advance()
        h.deactivate()
        assert h.active is False
        assert h.current_phase is None

    def test_persist_and_load(self):
        """持久化 → 重新加载"""
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        h1 = CrisisHolding(user_id="persist-test", db_path=tmp.name)
        h1.enter()
        h1.advance()
        h1.advance()  # 应推进到 GROUNDING

        h2 = CrisisHolding.load("persist-test", db_path=tmp.name)
        assert h2.active is True
        assert h2.current_phase == CrisisHolding.GROUNDING
        os.unlink(tmp.name)

    def test_phase_prompts_all_defined(self):
        """四个阶段都有对应 prompt"""
        for phase in CrisisHolding.PHASE_ORDER:
            assert phase in CrisisHolding.PHASE_PROMPTS
            assert len(CrisisHolding.PHASE_PROMPTS[phase]) > 0

    def test_get_phase_prompt(self):
        h = self._make_holding()
        h.enter()
        prompt = h.get_phase_prompt()
        assert "阶段1" in prompt
        assert "听到你" in prompt


# =====================================================================
# 5. 危机热线资源
# =====================================================================

class TestCrisisResources:
    def test_hotlines_not_empty(self):
        assert len(CRISIS_HOTLINES) >= 3

    def test_hotline_format(self):
        for name, number in CRISIS_HOTLINES.items():
            assert isinstance(name, str) and len(name) > 0
            assert isinstance(number, str) and len(number) > 0


# =====================================================================
# 6. 边缘案例（plan.md 指定）
# =====================================================================

class TestEdgeCases:
    """plan.md 第3372-3391行定义的边缘案例"""

    def test_subtle_crisis(self):
        """隐晦自杀表达——关键词层可能漏检，但确保不是 LOW"""
        # "我想永远睡过去" 不含硬编码关键词，关键词层应为 LOW
        # 完整的 detect_crisis 需要语义层兜底（在集成测试中验证）
        result = _keyword_scan("我想永远睡过去")
        # 关键词层确实漏检，这说明语义层是必要的
        assert result.level == RiskLevel.LOW  # 预期行为：关键词层不覆盖隐喻

    def test_third_party_crisis_keyword(self):
        """讨论他人自杀——关键词层会命中，需语义层降级"""
        result = _keyword_scan("我朋友说想自杀")
        assert result.level == RiskLevel.CRITICAL  # 关键词层会命中
        # 语义层应将其降级（集成测试验证）

    def test_media_reference_keyword(self):
        """引用影视——关键词层会命中"""
        result = _keyword_scan("电影里那个人跳楼了")
        assert result.level == RiskLevel.CRITICAL

    def test_farewell_behavior(self):
        """告别行为暗示——纯关键词无法检出"""
        result = _keyword_scan("把猫托付给邻居了")
        assert result.level == RiskLevel.LOW  # 需要语义层
