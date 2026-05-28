"""
端到端流水线评测器
一条输入 → 情绪识别 → 认知扭曲检测 → 危机检测 → 策略规划，全部评测
策略规划与标准答案对比，而非上游一致性检查
"""
import asyncio
import json
import sys
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from collections import defaultdict

# 让 server/ 目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from assessment.emotion import assess_emotion
from assessment.distortion import detect_distortion, DistortionResult
from safety.crisis_detector import detect_crisis, RiskLevel
from intervention.strategy_planner import plan_intervention

from evaluation.mappings import (
    emotion_matches,
    normalize_distortion,
    distortion_matches,
    normalize_risk_level,
    normalize_approach,
    normalize_valence,
    technique_matches,
)


@dataclass
class ModuleResult:
    case_id: str
    module: str                # "emotion" / "distortion" / "crisis" / "strategy"
    input_text: str
    expected: dict
    actual: dict
    passed: bool
    score: float               # 0-1
    details: str               # 详细对比说明
    needs_human_review: bool   # 是否需要人工复核


@dataclass
class PipelineResult:
    """一条输入的端到端评测结果"""
    case_id: str
    input_text: str
    source: str
    module_results: list[ModuleResult] = field(default_factory=list)

    @property
    def overall_score(self) -> float:
        if not self.module_results:
            return 0.0
        return sum(r.score for r in self.module_results) / len(self.module_results)

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.module_results)

    @property
    def needs_review(self) -> bool:
        return any(r.needs_human_review for r in self.module_results)


# ═══════════════════════════════════════════════════
# 单模块评测函数（使用 mappings.py）
# ═══════════════════════════════════════════════════

def _eval_emotion(case_id: str, input_text: str, expected: dict) -> ModuleResult:
    """评测情绪识别"""
    actual = assess_emotion(input_text)

    emotion_ok = emotion_matches(expected["primary_emotion"], actual["primary_emotion"])
    lo, hi = expected["intensity_range"]
    intensity_ok = lo <= actual.get("intensity", 0) <= hi
    valence_ok = normalize_valence(expected["valence"]) == normalize_valence(actual.get("valence", ""))

    score = 0.5 * int(emotion_ok) + 0.3 * int(intensity_ok) + 0.2 * int(valence_ok)
    passed = emotion_ok and intensity_ok and valence_ok

    details_parts = []
    if not emotion_ok:
        details_parts.append(
            f"情绪类型不匹配: 期望'{expected['primary_emotion']}', 实际'{actual['primary_emotion']}'"
        )
    if not intensity_ok:
        details_parts.append(
            f"强度超范围: 期望[{lo}-{hi}], 实际{actual.get('intensity', '?')}"
        )
    if not valence_ok:
        details_parts.append(
            f"效价不匹配: 期望'{expected['valence']}', 实际'{actual.get('valence', '?')}'"
        )

    return ModuleResult(
        case_id=case_id,
        module="emotion",
        input_text=input_text,
        expected=expected,
        actual=actual,
        passed=passed,
        score=score,
        details="; ".join(details_parts) if details_parts else "全部匹配",
        needs_human_review=not emotion_ok,
    )


def _eval_distortion(case_id: str, input_text: str, expected: dict) -> ModuleResult:
    """评测认知扭曲检测"""
    raw_results: list[DistortionResult] = detect_distortion(input_text)

    actual_detected = len(raw_results) > 0
    actual_types = [r.distortion_type for r in raw_results]
    actual = {
        "detected": actual_detected,
        "types": actual_types,
        "count": len(raw_results),
        "details": [
            {"type": r.distortion_type, "evidence": r.evidence, "confidence": r.confidence}
            for r in raw_results
        ],
    }

    should_detect = expected["should_detect"]
    details_parts = []

    if should_detect:
        detection_ok = actual_detected
        if not detection_ok:
            details_parts.append("未检出任何认知扭曲（期望检出）")

        min_det = expected.get("min_detections", 1)
        count_ok = len(raw_results) >= min_det

        expected_types = expected.get("types", [])
        type_matched = False
        if expected_types:
            for et in expected_types:
                for at in actual_types:
                    if distortion_matches(et, at):
                        type_matched = True
                        break
                if type_matched:
                    break
            if not type_matched and detection_ok:
                details_parts.append(
                    f"类型不匹配: 期望{expected_types}, 实际{actual_types}"
                )
        else:
            type_matched = True

        passed = detection_ok and count_ok and type_matched
        score = 0.4 * int(detection_ok) + 0.3 * int(type_matched) + 0.3 * int(count_ok)
    else:
        passed = not actual_detected
        score = 1.0 if passed else 0.0
        if not passed:
            details_parts.append(f"误报：检出了{actual_types}（期望无扭曲）")

    return ModuleResult(
        case_id=case_id,
        module="distortion",
        input_text=input_text,
        expected=expected,
        actual=actual,
        passed=passed,
        score=score,
        details="; ".join(details_parts) if details_parts else "判断正确",
        needs_human_review=not passed and should_detect,
    )


async def _eval_crisis(case_id: str, input_text: str, expected: dict) -> ModuleResult:
    """评测危机检测"""
    assessment = await detect_crisis(input_text)

    actual = {
        "level": assessment.level.value,
        "matched_keywords": assessment.matched_keywords,
        "semantic_confirmed": assessment.semantic_confirmed,
        "recommended_action": assessment.recommended_action,
    }

    expected_level = normalize_risk_level(expected["level"])
    actual_level = normalize_risk_level(assessment.level.value)

    level_order = ["low", "medium", "high", "critical"]
    expected_idx = level_order.index(expected_level)
    actual_idx = level_order.index(actual_level)
    diff = abs(expected_idx - actual_idx)

    if diff == 0:
        level_score = 1.0
    elif diff == 1:
        level_score = 0.5
    else:
        level_score = 0.0

    keyword_expected = expected.get("should_match_keywords", False)
    keyword_actual = len(assessment.matched_keywords) > 0
    keyword_ok = keyword_expected == keyword_actual
    keyword_score = 1.0 if keyword_ok else 0.0

    score = 0.7 * level_score + 0.3 * keyword_score
    passed = diff == 0

    details_parts = []
    if diff > 0:
        details_parts.append(
            f"风险等级偏差: 期望'{expected['level']}', 实际'{assessment.level.value}'"
        )
    if not keyword_ok:
        details_parts.append(
            f"关键词匹配: 期望{'命中' if keyword_expected else '未命中'}, "
            f"实际{'命中' if keyword_actual else '未命中'}"
        )

    is_false_negative = expected_idx > actual_idx and expected_level in ("critical", "high")

    return ModuleResult(
        case_id=case_id,
        module="crisis",
        input_text=input_text,
        expected=expected,
        actual=actual,
        passed=passed,
        score=score,
        details="; ".join(details_parts) if details_parts else "判断正确",
        needs_human_review=is_false_negative or (not passed and expected_level == "critical"),
    )


def _eval_strategy(
    case_id: str,
    input_text: str,
    expected_strategy: dict,
    emotion_result: dict,
    distortion_results: list[DistortionResult],
    crisis_level: str,
) -> ModuleResult:
    """
    基于标准答案评测策略规划。
    用上游模块实际输出推导 emotion_state，然后调用 plan_intervention，
    最终与 expected_strategy 中的标准答案对比。
    """
    # 从情绪识别结果推导 emotion_state
    intensity = emotion_result.get("intensity", 5)
    valence = normalize_valence(emotion_result.get("valence", "neutral"))
    crisis_normalized = normalize_risk_level(crisis_level)

    if crisis_normalized in ("critical", "high"):
        emotion_state = "crisis"
    elif valence == "negative" and intensity >= 6:
        emotion_state = "distressed"
    elif valence == "positive":
        emotion_state = "positive"
    elif valence == "negative":
        emotion_state = "diffuse"
    else:
        emotion_state = "normal"

    # 从认知扭曲结果提取类型
    distortion_type = ""
    if distortion_results:
        distortion_type = distortion_results[0].distortion_type

    plan = plan_intervention(
        emotion_state=emotion_state,
        distortion_type=distortion_type,
        session_count=0,
        user_readiness="ready",
    )

    actual = {
        "derived_emotion_state": emotion_state,
        "derived_distortion_type": distortion_type,
        "phase": plan.phase.value,
        "primary_approach": plan.primary_approach,
        "recommended_techniques": plan.recommended_techniques,
        "conversation_guidance": plan.conversation_guidance[:100] + "...",
    }

    # 与标准答案对比
    details_parts = []

    # 对比策略方向
    approach_ok = normalize_approach(expected_strategy["primary_approach"]) == normalize_approach(plan.primary_approach)
    if not approach_ok:
        details_parts.append(
            f"策略不匹配: 期望'{expected_strategy['primary_approach']}', 实际'{plan.primary_approach}'"
        )

    # 对比推荐技术
    expected_techniques = expected_strategy.get("should_include_techniques", [])
    technique_ok = True
    if expected_techniques:
        for tech in expected_techniques:
            if not technique_matches(tech, plan.recommended_techniques):
                technique_ok = False
                details_parts.append(
                    f"缺少技术'{tech}': 实际包含{plan.recommended_techniques}"
                )

    passed = approach_ok and technique_ok
    score = 0.6 * int(approach_ok) + 0.4 * int(technique_ok)

    return ModuleResult(
        case_id=case_id,
        module="strategy",
        input_text=input_text,
        expected=expected_strategy,
        actual=actual,
        passed=passed,
        score=score,
        details="; ".join(details_parts) if details_parts else "策略匹配",
        needs_human_review=not passed,
    )


# ═══════════════════════════════════════════════════
# 端到端流水线
# ═══════════════════════════════════════════════════

async def eval_pipeline_case(case: dict) -> PipelineResult:
    """
    对单条用例运行完整的端到端流水线评测。

    流程: input → 情绪 → 扭曲 → 危机 → 策略（与标准答案对比）
    """
    case_id = case["id"]
    input_text = case["input"]
    source = case.get("source", "")

    result = PipelineResult(case_id=case_id, input_text=input_text, source=source)

    # 1. 情绪识别
    emotion_actual = assess_emotion(input_text)
    if "expected_emotion" in case:
        result.module_results.append(
            _eval_emotion(case_id, input_text, case["expected_emotion"])
        )

    # 2. 认知扭曲检测
    distortion_raw: list[DistortionResult] = detect_distortion(input_text)
    if "expected_distortion" in case:
        result.module_results.append(
            _eval_distortion(case_id, input_text, case["expected_distortion"])
        )

    # 3. 危机检测
    crisis_assessment = await detect_crisis(input_text)
    if "expected_crisis" in case:
        result.module_results.append(
            await _eval_crisis(case_id, input_text, case["expected_crisis"])
        )

    # 4. 策略规划（与标准答案对比）
    if "expected_strategy" in case:
        result.module_results.append(
            _eval_strategy(
                case_id=case_id,
                input_text=input_text,
                expected_strategy=case["expected_strategy"],
                emotion_result=emotion_actual,
                distortion_results=distortion_raw,
                crisis_level=crisis_assessment.level.value,
            )
        )

    return result


# ═══════════════════════════════════════════════════
# 独立策略用例评测（保留手写策略用例支持）
# ═══════════════════════════════════════════════════

def eval_strategy_standalone(cases: list[dict]) -> list[ModuleResult]:
    """评测手写的策略规划用例（使用 mappings.py 归一化）"""
    results = []
    for case in cases:
        case_id = case["id"]
        expected = case["expected"]

        plan = plan_intervention(
            emotion_state=case["emotion_state"],
            distortion_type=case.get("distortion_type", ""),
            session_count=case.get("session_count", 0),
            user_readiness=case.get("user_readiness", "ready"),
        )

        actual = {
            "phase": plan.phase.value,
            "primary_approach": plan.primary_approach,
            "recommended_techniques": plan.recommended_techniques,
            "conversation_guidance": plan.conversation_guidance[:100] + "...",
        }

        input_desc = (
            f"emotion={case['emotion_state']}, "
            f"distortion={case.get('distortion_type', '')}, "
            f"sessions={case.get('session_count', 0)}, "
            f"readiness={case.get('user_readiness', 'unknown')}"
        )

        # 使用 mappings.py 归一化后对比
        approach_ok = normalize_approach(expected["primary_approach"]) == normalize_approach(plan.primary_approach)
        details_parts = []
        if not approach_ok:
            details_parts.append(
                f"策略不匹配: 期望'{expected['primary_approach']}', 实际'{plan.primary_approach}'"
            )

        expected_techniques = expected.get("should_include_techniques", [])
        technique_ok = True
        if expected_techniques:
            for tech in expected_techniques:
                if not technique_matches(tech, plan.recommended_techniques):
                    technique_ok = False
                    details_parts.append(
                        f"缺少技术'{tech}': 实际包含{plan.recommended_techniques}"
                    )

        passed = approach_ok and technique_ok
        score = 0.6 * int(approach_ok) + 0.4 * int(technique_ok)

        results.append(ModuleResult(
            case_id=case_id,
            module="strategy",
            input_text=input_desc,
            expected=expected,
            actual=actual,
            passed=passed,
            score=score,
            details="; ".join(details_parts) if details_parts else "策略匹配",
            needs_human_review=False,
        ))

    return results


# ═══════════════════════════════════════════════════
# 统一入口
# ═══════════════════════════════════════════════════

async def run_module_evaluation(data_dir: str | None = None) -> tuple[list[PipelineResult], list[ModuleResult]]:
    """
    运行全部模块评测。

    返回:
        (pipeline_results, strategy_standalone_results)
        - pipeline_results: 端到端流水线结果列表
        - strategy_standalone_results: 独立策略用例结果列表

    data_dir: 测试用例目录，默认为 evaluation/data/
    """
    if data_dir is None:
        data_dir = str(Path(__file__).parent / "data")

    cases_path = os.path.join(data_dir, "module_cases.json")
    with open(cases_path, "r", encoding="utf-8") as f:
        cases_data = json.load(f)

    # ── 端到端流水线评测（统一格式） ──
    unified_cases = cases_data.get("cases", [])
    total = len(unified_cases)
    print(f"[端到端评测] 共 {total} 条统一用例")

    pipeline_results: list[PipelineResult] = []
    for i, case in enumerate(unified_cases, 1):
        print(f"[端到端评测] ({i}/{total}) {case['id']}: {case['input'][:30]}...")
        result = await eval_pipeline_case(case)
        pipeline_results.append(result)

    # ── 独立策略用例 ──
    strategy_cases = cases_data.get("strategy", [])
    strategy_results: list[ModuleResult] = []
    if strategy_cases:
        print(f"[策略评测] {len(strategy_cases)} 条独立用例")
        strategy_results = eval_strategy_standalone(strategy_cases)

    return pipeline_results, strategy_results


def get_all_module_results(
    pipeline_results: list[PipelineResult],
    strategy_results: list[ModuleResult],
) -> list[ModuleResult]:
    """将所有结果扁平化为 ModuleResult 列表（兼容旧的报告生成器）"""
    all_results = []
    for pr in pipeline_results:
        all_results.extend(pr.module_results)
    all_results.extend(strategy_results)
    return all_results


def print_summary(
    pipeline_results: list[PipelineResult],
    strategy_results: list[ModuleResult],
) -> None:
    """打印评测结果摘要"""
    print("\n" + "=" * 60)
    print("评测结果摘要")
    print("=" * 60)

    # 按模块统计
    module_stats: dict[str, dict] = defaultdict(lambda: {"total": 0, "passed": 0, "score_sum": 0.0})

    for pr in pipeline_results:
        for mr in pr.module_results:
            stats = module_stats[mr.module]
            stats["total"] += 1
            stats["passed"] += int(mr.passed)
            stats["score_sum"] += mr.score

    for mr in strategy_results:
        stats = module_stats["strategy_standalone"]
        stats["total"] += 1
        stats["passed"] += int(mr.passed)
        stats["score_sum"] += mr.score

    for module, stats in module_stats.items():
        total = stats["total"]
        passed = stats["passed"]
        avg_score = stats["score_sum"] / total if total > 0 else 0
        print(f"\n  {module}:")
        print(f"    通过率: {passed}/{total} ({100 * passed / total:.1f}%)")
        print(f"    平均分: {avg_score:.2f}")

    # 端到端总览
    e2e_total = len(pipeline_results)
    e2e_all_passed = sum(1 for pr in pipeline_results if pr.all_passed)
    e2e_avg = sum(pr.overall_score for pr in pipeline_results) / e2e_total if e2e_total > 0 else 0
    need_review = sum(1 for pr in pipeline_results if pr.needs_review)

    print(f"\n  端到端总览:")
    print(f"    全通过: {e2e_all_passed}/{e2e_total}")
    print(f"    平均分: {e2e_avg:.2f}")
    print(f"    需人工复核: {need_review}")
    print("=" * 60)
