"""
评估模块测试——test_assessment.py
覆盖：量表加载/评分/安全检查、情绪评估解析、认知扭曲关键词预筛
"""
import pytest
import json
from unittest.mock import MagicMock

from assessment.scales import (
    load_scale,
    score_scale,
    get_scale_intro,
    get_next_item,
    format_result_for_agent,
    ScaleResult,
)
from assessment.emotion import (
    _parse_emotion_response,
    EMOTION_CATEGORIES,
)
from assessment.distortion import (
    detect_distortion,
    KEYWORD_PATTERNS,
    _parse_distortion_response,
)


# =====================================================================
# 1. 量表加载
# =====================================================================

class TestScaleLoading:

    def test_load_phq9(self):
        scale = load_scale("PHQ-9")
        assert scale["name"] == "PHQ-9"
        assert len(scale["items"]) == 9
        assert len(scale["options"]) == 4

    def test_load_gad7(self):
        scale = load_scale("GAD-7")
        assert scale["name"] == "GAD-7"
        assert len(scale["items"]) == 7
        assert len(scale["options"]) == 4

    def test_load_unsupported_scale(self):
        with pytest.raises(ValueError, match="不支持的量表"):
            load_scale("UNKNOWN-99")

    def test_scale_options_values(self):
        """选项值应为 0-3"""
        for name in ["PHQ-9", "GAD-7"]:
            scale = load_scale(name)
            values = [o["value"] for o in scale["options"]]
            assert values == [0, 1, 2, 3]

    def test_scale_scoring_ranges_complete(self):
        """评分区间应覆盖 0 到 total_max"""
        for name in ["PHQ-9", "GAD-7"]:
            scale = load_scale(name)
            ranges = scale["scoring"]["ranges"]
            assert ranges[0]["min"] == 0
            assert ranges[-1]["max"] == scale["scoring"]["total_max"]


# =====================================================================
# 2. 量表评分
# =====================================================================

class TestScaleScoring:

    def test_phq9_no_depression(self):
        result = score_scale("PHQ-9", [0, 0, 0, 0, 0, 0, 0, 0, 0])
        assert result.total_score == 0
        assert result.category == "none"
        assert result.label == "无抑郁"
        assert len(result.safety_alerts) == 0

    def test_phq9_mild(self):
        result = score_scale("PHQ-9", [1, 1, 1, 1, 1, 0, 0, 0, 0])
        assert result.total_score == 5
        assert result.category == "mild"

    def test_phq9_moderate(self):
        result = score_scale("PHQ-9", [2, 2, 1, 1, 1, 1, 1, 1, 0])
        assert result.total_score == 10
        assert result.category == "moderate"

    def test_phq9_mod_severe(self):
        result = score_scale("PHQ-9", [2, 2, 2, 2, 2, 2, 2, 1, 0])
        assert result.total_score == 15
        assert result.category == "mod_severe"

    def test_phq9_severe(self):
        result = score_scale("PHQ-9", [3, 3, 3, 3, 3, 3, 3, 3, 3])
        assert result.total_score == 27
        assert result.category == "severe"
        assert result.label == "重度抑郁"

    def test_phq9_item9_safety_alert(self):
        """第9题得分>0 触发安全告警"""
        result = score_scale("PHQ-9", [0, 0, 0, 0, 0, 0, 0, 0, 1])
        assert result.total_score == 1
        assert result.category == "none"  # 总分仍低
        assert len(result.safety_alerts) == 1
        alert = result.safety_alerts[0]
        assert alert["item_id"] == 9
        assert alert["score"] == 1

    def test_phq9_item9_zero_no_alert(self):
        """第9题得分=0 不触发"""
        result = score_scale("PHQ-9", [3, 3, 3, 3, 3, 3, 3, 3, 0])
        assert len(result.safety_alerts) == 0

    def test_gad7_no_anxiety(self):
        result = score_scale("GAD-7", [0, 0, 0, 0, 0, 0, 0])
        assert result.total_score == 0
        assert result.category == "none"
        assert result.label == "无焦虑"

    def test_gad7_severe(self):
        result = score_scale("GAD-7", [3, 3, 3, 3, 3, 3, 3])
        assert result.total_score == 21
        assert result.category == "severe"

    def test_gad7_no_safety_alerts(self):
        """GAD-7 没有 safety_items"""
        result = score_scale("GAD-7", [3, 3, 3, 3, 3, 3, 3])
        assert len(result.safety_alerts) == 0

    def test_wrong_answer_count(self):
        with pytest.raises(ValueError, match="需要 9 个回答"):
            score_scale("PHQ-9", [1, 2, 3])

    def test_wrong_answer_count_gad7(self):
        with pytest.raises(ValueError, match="需要 7 个回答"):
            score_scale("GAD-7", [1, 2])


# =====================================================================
# 3. 量表流程
# =====================================================================

class TestScaleFlow:

    def test_get_intro(self):
        intro = get_scale_intro("PHQ-9")
        assert intro["scale"] == "PHQ-9"
        assert intro["total_items"] == 9
        assert intro["current_item"]["id"] == 1
        assert intro["current_item"]["index"] == 0

    def test_get_next_items(self):
        """逐题获取"""
        for i in range(8):
            item = get_next_item("PHQ-9", i)
            assert item is not None
            assert item["id"] == i + 2
            assert item["index"] == i + 1

    def test_get_next_after_last(self):
        """最后一题后返回 None"""
        assert get_next_item("PHQ-9", 8) is None
        assert get_next_item("GAD-7", 6) is None

    def test_format_result_normal(self):
        result = ScaleResult(
            scale_name="PHQ-9", total_score=5, max_score=27,
            category="mild", label="轻度抑郁",
            answers=[1, 1, 1, 1, 1, 0, 0, 0, 0],
        )
        formatted = format_result_for_agent(result)
        data = json.loads(formatted)
        assert data["total_score"] == 5
        assert "safety_alerts" not in data

    def test_format_result_with_safety(self):
        result = ScaleResult(
            scale_name="PHQ-9", total_score=15, max_score=27,
            category="mod_severe", label="中重度抑郁",
            answers=[2, 2, 2, 2, 2, 2, 2, 0, 1],
            safety_alerts=[{"item_id": 9, "score": 1, "action": "trigger", "note": "test"}],
        )
        formatted = format_result_for_agent(result)
        data = json.loads(formatted)
        assert data["requires_safety_protocol"] is True
        assert len(data["safety_alerts"]) == 1


# =====================================================================
# 4. 情绪评估——解析逻辑（不调用 LLM）
# =====================================================================

class TestEmotionParsing:

    def _make_response(self, text: str):
        mock = MagicMock()
        mock.content = [MagicMock(text=text)]
        return mock

    def test_parse_valid(self):
        resp = self._make_response(
            '{"primary_emotion": "焦虑", "intensity": 7, '
            '"secondary_emotions": ["恐惧"], "valence": "消极"}'
        )
        result = _parse_emotion_response(resp)
        assert result["primary_emotion"] == "焦虑"
        assert result["intensity"] == 7
        assert result["valence"] == "消极"

    def test_parse_english_valence_mapped_to_cn(self):
        """LLM 偶尔输出英文 valence，应自动映射为中文"""
        resp = self._make_response(
            '{"primary_emotion": "焦虑", "intensity": 7, '
            '"secondary_emotions": ["恐惧"], "valence": "negative"}'
        )
        result = _parse_emotion_response(resp)
        assert result["valence"] == "消极"

    def test_parse_clamps_intensity(self):
        resp = self._make_response(
            '{"primary_emotion": "开心", "intensity": 15, '
            '"secondary_emotions": [], "valence": "积极"}'
        )
        result = _parse_emotion_response(resp)
        assert result["intensity"] == 10  # clamped

    def test_parse_invalid_json(self):
        resp = self._make_response("not json")
        result = _parse_emotion_response(resp)
        assert result["primary_emotion"] == "未知"
        assert result["valence"] == "中性"

    def test_emotion_categories_coverage(self):
        """情绪分类体系应包含三个大类"""
        assert "negative" in EMOTION_CATEGORIES
        assert "positive" in EMOTION_CATEGORIES
        assert "neutral" in EMOTION_CATEGORIES
        total = sum(len(v) for v in EMOTION_CATEGORIES.values())
        assert total >= 15  # 至少 15 种情绪


# =====================================================================
# 5. 认知扭曲——关键词预筛（不调用 LLM）
# =====================================================================

class TestDistortionKeywords:

    def test_all_or_nothing_pattern(self):
        """'总是' 应触发全或无思维候选"""
        import re
        info = KEYWORD_PATTERNS["all_or_nothing"]
        assert any(re.search(p, "我总是做不好") for p in info["patterns"])

    def test_mind_reading_pattern(self):
        import re
        info = KEYWORD_PATTERNS["mind_reading"]
        assert any(re.search(p, "他肯定觉得我很蠢") for p in info["patterns"])

    def test_fortune_telling_pattern(self):
        import re
        info = KEYWORD_PATTERNS["fortune_telling"]
        assert any(re.search(p, "这次面试肯定会搞砸") for p in info["patterns"])

    def test_15_distortion_types(self):
        """应有 15 种认知扭曲"""
        assert len(KEYWORD_PATTERNS) == 15

    def test_each_type_has_patterns(self):
        for key, info in KEYWORD_PATTERNS.items():
            assert "name" in info
            assert "name_en" in info
            assert len(info["patterns"]) > 0

    def test_positive_context_still_matches(self):
        """积极语境——'我总是很开心' 正则层会命中，但语义层应排除"""
        import re
        info = KEYWORD_PATTERNS["all_or_nothing"]
        assert any(re.search(p, "我总是很开心") for p in info["patterns"])

    def test_pattern_catches_variants(self):
        """正则应匹配关键词变体"""
        import re
        # "从来不" 是 "从不" 的变体
        info = KEYWORD_PATTERNS["all_or_nothing"]
        assert any(re.search(p, "我从来不被重视") for p in info["patterns"])
        # "每回都" 是 "每次都" 的变体
        info = KEYWORD_PATTERNS["overgeneralization"]
        assert any(re.search(p, "每回都这样") for p in info["patterns"])
        # "我真是个" 是 "我就是个" 的变体
        info = KEYWORD_PATTERNS["labeling"]
        assert any(re.search(p, "我真是个废物") for p in info["patterns"])


class TestDistortionParsing:

    def _make_response(self, text: str):
        mock = MagicMock()
        mock.content = [MagicMock(text=text)]
        return mock

    def test_parse_confirmed(self):
        resp = self._make_response(
            '[{"type": "全或无思维", "type_en": "All-or-Nothing Thinking", '
            '"evidence": "我永远做不好", "confidence": 0.85}]'
        )
        results = _parse_distortion_response(resp, ["all_or_nothing"])
        assert len(results) == 1
        assert results[0].detected is True
        assert results[0].confidence == 0.85

    def test_parse_empty_array(self):
        """语义确认无扭曲"""
        resp = self._make_response("[]")
        results = _parse_distortion_response(resp, ["all_or_nothing"])
        assert len(results) == 0

    def test_parse_invalid_json(self):
        resp = self._make_response("invalid")
        results = _parse_distortion_response(resp, ["all_or_nothing"])
        assert len(results) == 0
