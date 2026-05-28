"""
HTML 评测报告生成器
生成包含仪表盘、端到端流水线详情、对话评分、人工复核项的完整报告
"""
import html
from datetime import datetime
from collections import defaultdict

from evaluation.eval_modules import ModuleResult, PipelineResult
from evaluation.eval_conversation import ConversationResult
from evaluation.mappings import approach_to_cn, techniques_to_cn, valence_to_cn, normalize_distortion


def _stars(score: int, max_score: int = 5) -> str:
    filled = "★" * score
    empty = "☆" * (max_score - score)
    return f'<span class="stars">{filled}{empty}</span> ({score})'


def _badge(passed: bool, needs_review: bool = False) -> str:
    if passed:
        return '<span class="badge pass">PASS</span>'
    if needs_review:
        return '<span class="badge review">REVIEW</span>'
    return '<span class="badge fail">FAIL</span>'


def _score_color(score: float) -> str:
    if score >= 0.8:
        return "var(--success)"
    if score >= 0.5:
        return "var(--warning)"
    return "var(--danger)"


def _esc(text: str) -> str:
    return html.escape(str(text))


def generate_report(
    module_results: list[ModuleResult] | None = None,
    conversation_results: list[ConversationResult] | None = None,
    pipeline_results: list[PipelineResult] | None = None,
    output_path: str = "eval_report.html",
) -> str:
    """生成 HTML 评测报告并写入文件，返回文件路径"""
    module_results = module_results or []
    conversation_results = conversation_results or []
    pipeline_results = pipeline_results or []

    stats = _compute_stats(module_results, conversation_results)

    sections = [
        _render_header(),
        _render_dashboard(stats),
    ]

    # 端到端流水线视图（优先使用）
    if pipeline_results:
        sections.append(_render_pipeline_details(pipeline_results))
    elif module_results:
        sections.append(_render_module_details(module_results, stats))

    if conversation_results:
        sections.append(_render_conversation_details(conversation_results))

    review_items = _collect_review_items(module_results, conversation_results)
    if review_items:
        sections.append(_render_review_section(review_items))

    sections.append(_render_footer())

    full_html = "\n".join(sections)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_html)

    return output_path


def _compute_stats(
    module_results: list[ModuleResult],
    conversation_results: list[ConversationResult],
) -> dict:
    stats = {
        "emotion": {"total": 0, "passed": 0, "avg_score": 0.0},
        "distortion": {"total": 0, "passed": 0, "avg_score": 0.0},
        "crisis": {"total": 0, "passed": 0, "avg_score": 0.0},
        "strategy": {"total": 0, "passed": 0, "avg_score": 0.0},
        "conversation": {"total": 0, "avg_score": 0.0, "avg_scores": {}},
    }

    for r in module_results:
        key = r.module if r.module in stats else "strategy"
        s = stats[key]
        s["total"] += 1
        if r.passed:
            s["passed"] += 1
        s["avg_score"] += r.score

    for module in ("emotion", "distortion", "crisis", "strategy"):
        s = stats[module]
        if s["total"] > 0:
            s["avg_score"] = s["avg_score"] / s["total"]

    if conversation_results:
        stats["conversation"]["total"] = len(conversation_results)
        all_dims = {}
        for cr in conversation_results:
            for dim, score in cr.scores.items():
                all_dims.setdefault(dim, []).append(score)
        stats["conversation"]["avg_scores"] = {
            dim: sum(scores) / len(scores) for dim, scores in all_dims.items()
        }
        all_scores = [s for scores in all_dims.values() for s in scores]
        stats["conversation"]["avg_score"] = sum(all_scores) / len(all_scores) if all_scores else 0

    return stats


def _render_header() -> str:
    return f"""\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>心理学Agent评测报告</title>
<style>
:root {{
    --primary: #4a90d9;
    --success: #27ae60;
    --warning: #f39c12;
    --danger: #e74c3c;
    --bg: #f5f7fa;
    --card-bg: #ffffff;
    --text: #2c3e50;
    --text-light: #7f8c8d;
    --border: #e0e6ed;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 24px;
}}
.container {{ max-width: 1200px; margin: 0 auto; }}
h1 {{
    text-align: center;
    font-size: 28px;
    margin-bottom: 4px;
    color: var(--primary);
}}
.subtitle {{
    text-align: center;
    color: var(--text-light);
    margin-bottom: 32px;
    font-size: 14px;
}}
.dashboard {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 32px;
}}
.metric-card {{
    background: var(--card-bg);
    border-radius: 12px;
    padding: 20px;
    text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    border: 1px solid var(--border);
}}
.metric-card .label {{ color: var(--text-light); font-size: 13px; margin-bottom: 8px; }}
.metric-card .value {{ font-size: 32px; font-weight: 700; }}
.metric-card .sub {{ color: var(--text-light); font-size: 12px; margin-top: 4px; }}
.value.high {{ color: var(--success); }}
.value.medium {{ color: var(--warning); }}
.value.low {{ color: var(--danger); }}
.section {{
    background: var(--card-bg);
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 24px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    border: 1px solid var(--border);
}}
.section h2 {{
    font-size: 20px;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 2px solid var(--border);
    cursor: pointer;
    user-select: none;
}}
.section h2:hover {{ color: var(--primary); }}
/* 端到端用例卡片 */
.pipeline-card {{
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 16px;
}}
.pipeline-card.all-passed {{ border-left: 4px solid var(--success); }}
.pipeline-card.has-failure {{ border-left: 4px solid var(--danger); }}
.pipeline-card.needs-review {{ border-left: 4px solid var(--warning); }}
.pipeline-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}}
.pipeline-header .case-id {{ font-weight: 600; font-family: monospace; font-size: 14px; }}
.pipeline-header .source {{ color: var(--text-light); font-size: 12px; }}
.pipeline-input {{
    background: var(--bg);
    border-radius: 6px;
    padding: 12px;
    margin-bottom: 12px;
    font-size: 14px;
    line-height: 1.5;
}}
.pipeline-input .label {{ font-weight: 600; font-size: 12px; color: var(--text-light); margin-bottom: 4px; }}
.module-results-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 12px;
}}
.module-result-card {{
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px;
    font-size: 13px;
}}
.module-result-card.passed {{ background: #f0faf0; }}
.module-result-card.failed {{ background: #fef0f0; }}
.module-result-card .module-name {{
    font-weight: 600;
    font-size: 14px;
    margin-bottom: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}}
.module-result-card .score-bar {{
    height: 4px;
    border-radius: 2px;
    background: var(--border);
    margin-bottom: 8px;
}}
.module-result-card .score-fill {{
    height: 100%;
    border-radius: 2px;
}}
.module-result-card .detail-row {{
    display: flex;
    justify-content: space-between;
    padding: 2px 0;
    border-bottom: 1px dotted var(--border);
}}
.module-result-card .detail-row:last-child {{ border-bottom: none; }}
.module-result-card .detail-row .k {{ color: var(--text-light); }}
/* 旧格式卡片 */
.case-card {{
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
}}
.case-card.passed {{ border-left: 4px solid var(--success); }}
.case-card.failed {{ border-left: 4px solid var(--danger); }}
.case-card.review {{ border-left: 4px solid var(--warning); }}
.case-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}}
.case-id {{ font-weight: 600; font-family: monospace; }}
.badge {{
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
}}
.badge.pass {{ background: #e8f5e9; color: #2e7d32; }}
.badge.fail {{ background: #ffebee; color: #c62828; }}
.badge.review {{ background: #fff3e0; color: #e65100; }}
.field {{ margin: 6px 0; }}
.field .label {{ font-weight: 500; color: var(--text-light); font-size: 13px; }}
.field .content {{ margin-top: 2px; }}
.comparison {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-top: 8px;
}}
.comparison > div {{
    background: var(--bg);
    border-radius: 6px;
    padding: 12px;
    font-size: 14px;
}}
.comparison .label {{ font-weight: 600; margin-bottom: 6px; }}
.scores-grid {{
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    margin: 12px 0;
}}
.score-item {{ min-width: 180px; }}
.score-item .dim {{ font-size: 13px; color: var(--text-light); }}
.stars {{ color: #f39c12; letter-spacing: 2px; }}
.red-flag {{
    background: #ffebee;
    color: #c62828;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 13px;
    display: inline-block;
    margin: 2px;
}}
.review-section {{ background: #fff3e0; border: 1px solid #ffe0b2; }}
.review-item {{
    padding: 8px 12px;
    margin: 6px 0;
    background: white;
    border-radius: 6px;
    font-size: 14px;
}}
details {{ margin: 4px 0; }}
summary {{ cursor: pointer; font-weight: 500; padding: 4px 0; }}
summary:hover {{ color: var(--primary); }}
.collapsible {{ display: none; }}
.collapsible.open {{ display: block; }}
.overall-score {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 600;
    font-size: 13px;
    color: white;
}}
</style>
<script>
function toggleSection(id) {{
    var el = document.getElementById(id);
    el.classList.toggle('open');
}}
</script>
</head>
<body>
<div class="container">
<h1>心理学Agent评测报告</h1>
<p class="subtitle">生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
"""


MODULE_LABELS = {
    "emotion": "情绪识别",
    "distortion": "认知扭曲",
    "crisis": "危机检测",
    "strategy": "策略规划",
    "strategy_standalone": "策略规划(独立)",
}


def _render_dashboard(stats: dict) -> str:
    cards = []

    for module, label in [("emotion", "情绪识别"), ("distortion", "认知扭曲"), ("crisis", "危机检测"), ("strategy", "策略规划")]:
        s = stats[module]
        if s["total"] == 0:
            continue
        pct = round(s["passed"] / s["total"] * 100)
        css = "high" if pct >= 80 else "medium" if pct >= 60 else "low"
        cards.append(f"""\
<div class="metric-card">
    <div class="label">{label}</div>
    <div class="value {css}">{pct}%</div>
    <div class="sub">{s['passed']}/{s['total']} 通过</div>
</div>""")

    if stats["conversation"]["total"] > 0:
        avg = stats["conversation"]["avg_score"]
        css = "high" if avg >= 4 else "medium" if avg >= 3 else "low"
        cards.append(f"""\
<div class="metric-card">
    <div class="label">对话质量</div>
    <div class="value {css}">{avg:.1f}</div>
    <div class="sub">{stats['conversation']['total']} 个场景</div>
</div>""")

    return f'<div class="dashboard">{"".join(cards)}</div>'


def _render_pipeline_details(results: list[PipelineResult]) -> str:
    """渲染端到端流水线详情——每条用例一张卡片，包含所有模块结果"""
    total = len(results)
    all_passed = sum(1 for r in results if r.all_passed)
    avg_score = sum(r.overall_score for r in results) / total if total > 0 else 0

    cards_html = []
    for pr in results:
        # 卡片样式
        if pr.all_passed:
            css_class = "all-passed"
        elif pr.needs_review:
            css_class = "needs-review"
        else:
            css_class = "has-failure"

        # 每个模块的结果小卡片
        module_cards = []
        for mr in pr.module_results:
            mr_css = "passed" if mr.passed else "failed"
            score_pct = int(mr.score * 100)
            score_color = _score_color(mr.score)
            module_label = MODULE_LABELS.get(mr.module, mr.module)

            # 构建期望vs实际对比行
            detail_rows = []
            if mr.module == "emotion":
                detail_rows.append(f'<div class="detail-row"><span class="k">期望情绪</span><span>{_esc(str(mr.expected.get("primary_emotion", "")))}</span></div>')
                detail_rows.append(f'<div class="detail-row"><span class="k">实际情绪</span><span>{_esc(str(mr.actual.get("primary_emotion", "")))}</span></div>')
                exp_range = mr.expected.get("intensity_range", [])
                detail_rows.append(f'<div class="detail-row"><span class="k">期望强度</span><span>{exp_range[0]}-{exp_range[1] if len(exp_range) > 1 else "?"}</span></div>')
                detail_rows.append(f'<div class="detail-row"><span class="k">实际强度</span><span>{_esc(str(mr.actual.get("intensity", "?")))}</span></div>')
                detail_rows.append(f'<div class="detail-row"><span class="k">期望效价</span><span>{valence_to_cn(str(mr.expected.get("valence", "")))}</span></div>')
                detail_rows.append(f'<div class="detail-row"><span class="k">实际效价</span><span>{valence_to_cn(str(mr.actual.get("valence", "")))}</span></div>')
            elif mr.module == "distortion":
                should = mr.expected.get("should_detect", False)
                detail_rows.append(f'<div class="detail-row"><span class="k">应检出</span><span>{"是" if should else "否"}</span></div>')
                if should:
                    exp_types = mr.expected.get("types", [])
                    exp_types_cn = [normalize_distortion(t) for t in exp_types]
                    detail_rows.append(f'<div class="detail-row"><span class="k">期望类型</span><span>{_esc(", ".join(exp_types_cn) if exp_types_cn else "任意")}</span></div>')
                actual_types = mr.actual.get("types", [])
                actual_types_cn = [normalize_distortion(t) for t in actual_types]
                detail_rows.append(f'<div class="detail-row"><span class="k">实际检出</span><span>{_esc(", ".join(actual_types_cn) if actual_types_cn else "无")}</span></div>')
            elif mr.module == "crisis":
                detail_rows.append(f'<div class="detail-row"><span class="k">期望等级</span><span>{_esc(str(mr.expected.get("level", "")))}</span></div>')
                detail_rows.append(f'<div class="detail-row"><span class="k">实际等级</span><span>{_esc(str(mr.actual.get("level", "")))}</span></div>')
                kw = mr.actual.get("matched_keywords", [])
                if kw:
                    detail_rows.append(f'<div class="detail-row"><span class="k">匹配关键词</span><span>{_esc(", ".join(kw))}</span></div>')
            elif mr.module == "strategy":
                # 期望
                exp_state = mr.expected.get("emotion_state", "")
                exp_approach = mr.expected.get("primary_approach", "")
                if exp_approach:
                    detail_rows.append(f'<div class="detail-row"><span class="k">期望策略</span><span>{approach_to_cn(exp_approach)}</span></div>')
                exp_techniques = mr.expected.get("should_include_techniques", [])
                if exp_techniques:
                    detail_rows.append(f'<div class="detail-row"><span class="k">期望技术</span><span>{_esc(", ".join(techniques_to_cn(exp_techniques)))}</span></div>')
                # 实际
                detail_rows.append(f'<div class="detail-row"><span class="k">推导情绪状态</span><span>{_esc(str(mr.actual.get("derived_emotion_state", mr.actual.get("phase", ""))))}</span></div>')
                detail_rows.append(f'<div class="detail-row"><span class="k">实际策略</span><span>{approach_to_cn(str(mr.actual.get("primary_approach", "")))}</span></div>')
                actual_techs = mr.actual.get("recommended_techniques", [])
                detail_rows.append(f'<div class="detail-row"><span class="k">实际技术</span><span>{_esc(", ".join(techniques_to_cn(actual_techs)))}</span></div>')

            badge = _badge(mr.passed, mr.needs_human_review)
            detail_rows_html = "".join(detail_rows)

            module_cards.append(f"""\
<div class="module-result-card {mr_css}">
    <div class="module-name">{module_label} {badge}</div>
    <div class="score-bar"><div class="score-fill" style="width:{score_pct}%; background:{score_color};"></div></div>
    {detail_rows_html}
    <div style="margin-top:6px; font-size:12px; color:var(--text-light);">{_esc(mr.details)}</div>
</div>""")

        overall_color = _score_color(pr.overall_score)
        overall_pct = int(pr.overall_score * 100)

        cards_html.append(f"""\
<div class="pipeline-card {css_class}">
    <div class="pipeline-header">
        <span>
            <span class="case-id">{_esc(pr.case_id)}</span>
            <span class="source">[{_esc(pr.source)}]</span>
        </span>
        <span class="overall-score" style="background:{overall_color};">{overall_pct}%</span>
    </div>
    <div class="pipeline-input">
        <div class="label">输入文本</div>
        {_esc(pr.input_text)}
    </div>
    <div class="module-results-grid">
        {"".join(module_cards)}
    </div>
</div>""")

    return f"""\
<div class="section">
    <h2 onclick="toggleSection('section_pipeline')">
        端到端流水线评测 ({all_passed}/{total} 全通过，平均 {avg_score:.0%})
    </h2>
    <div id="section_pipeline" class="collapsible open">
        {"".join(cards_html)}
    </div>
</div>"""


def _render_module_details(results: list[ModuleResult], stats: dict) -> str:
    """旧格式：按模块分组显示"""
    sections = []

    for module, label in [("emotion", "情绪识别"), ("distortion", "认知扭曲检测"), ("crisis", "危机检测"), ("strategy", "策略规划")]:
        items = [r for r in results if r.module == module]
        if not items:
            continue

        s = stats[module]
        section_id = f"section_{module}"

        cards_html = []
        for r in items:
            css_class = "passed" if r.passed else ("review" if r.needs_human_review else "failed")
            badge = _badge(r.passed, r.needs_human_review)

            cards_html.append(f"""\
<div class="case-card {css_class}">
    <div class="case-header">
        <span class="case-id">{_esc(r.case_id)}</span>
        {badge}
    </div>
    <div class="field">
        <div class="label">输入</div>
        <div class="content">{_esc(r.input_text)}</div>
    </div>
    <div class="comparison">
        <div><div class="label">期望</div>{_esc(str(r.expected))}</div>
        <div><div class="label">实际</div>{_esc(str(r.actual))}</div>
    </div>
    <div class="field">
        <div class="label">评判</div>
        <div class="content">{_esc(r.details)} (得分: {r.score:.2f})</div>
    </div>
</div>""")

        sections.append(f"""\
<div class="section">
    <h2 onclick="toggleSection('{section_id}')">
        {label} ({s['passed']}/{s['total']} 通过，平均 {s['avg_score']:.0%})
    </h2>
    <div id="{section_id}" class="collapsible {'open' if len(items) <= 10 else ''}">
        {"".join(cards_html)}
    </div>
</div>""")

    return "\n".join(sections)


def _render_conversation_details(results: list[ConversationResult]) -> str:
    cards = []

    for cr in results:
        # 渲染逐轮对比：来访者 → 原文回复 vs Agent回复
        dialogue_html_parts = []
        for i in range(cr.turn_count):
            turn_num = i + 1
            user_msg = cr.user_messages[i] if i < len(cr.user_messages) else ""
            agent_resp = cr.agent_responses[i] if i < len(cr.agent_responses) else ""
            ref_resp = cr.reference_responses[i] if i < len(cr.reference_responses) else ""

            dialogue_html_parts.append(f"""\
<div style="margin:12px 0;border:1px solid var(--border);border-radius:8px;overflow:hidden;">
    <div style="background:#e3f2fd;padding:8px 12px;font-size:13px;">
        <b>第{turn_num}轮 · 来访者:</b> {_esc(user_msg)}
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:0;">
        <div style="padding:8px 12px;background:#fff8e1;border-right:1px solid var(--border);font-size:13px;">
            <div style="font-weight:600;color:#e65100;margin-bottom:4px;">原文咨询师</div>
            {_esc(ref_resp) if ref_resp else '<span style="color:var(--text-light);">无原文</span>'}
        </div>
        <div style="padding:8px 12px;background:#f1f8e9;font-size:13px;">
            <div style="font-weight:600;color:#2e7d32;margin-bottom:4px;">AI咨询师</div>
            {_esc(agent_resp) if agent_resp else '<span style="color:var(--text-light);">无回复</span>'}
        </div>
    </div>
</div>"""
            )

        dialogue_html = "".join(dialogue_html_parts)

        scores_html = "".join(
            f'<div class="score-item"><div class="dim">{_dim_label(dim)}</div>{_stars(score)}</div>'
            for dim, score in cr.scores.items()
        )

        red_flags_html = ""
        if cr.red_flags_found:
            flags = "".join(f'<span class="red-flag">{_esc(rf)}</span>' for rf in cr.red_flags_found)
            red_flags_html = f'<div class="field"><div class="label">发现的 Red Flags</div><div class="content">{flags}</div></div>'

        css_class = "review" if cr.needs_human_review else "passed"

        suggestions_html = ""
        if cr.improvement_suggestions:
            items = "".join(f"<li>{_esc(s)}</li>" for s in cr.improvement_suggestions)
            suggestions_html = f'<div class="field"><div class="label">改进建议</div><ul>{items}</ul></div>'

        reasoning_html = ""
        if cr.reasoning:
            parts = []
            for dim, reason in cr.reasoning.items():
                if dim not in ("error", "parse_error"):
                    parts.append(f"<li><b>{_dim_label(dim)}:</b> {_esc(str(reason))}</li>")
            if parts:
                reasoning_html = f'<div class="field"><div class="label">评分理由</div><ul>{"".join(parts)}</ul></div>'

        cards.append(f"""\
<div class="case-card {css_class}">
    <div class="case-header">
        <span class="case-id">{_esc(cr.case_id)}: {_esc(cr.scenario)} ({cr.turn_count}轮)</span>
        {_badge(not cr.needs_human_review, cr.needs_human_review)}
    </div>
    <div class="field">
        <div class="label">完整对话记录</div>
        <div class="content" style="max-height:400px;overflow-y:auto;border:1px solid var(--border);border-radius:8px;padding:12px;">
            {dialogue_html}
        </div>
    </div>
    <div class="scores-grid">{scores_html}</div>
    {red_flags_html}
    <div class="field">
        <div class="label">总体评语</div>
        <div class="content">{_esc(cr.overall_comment)}</div>
    </div>
    {reasoning_html}
    {suggestions_html}
</div>""")

    return f"""\
<div class="section">
    <h2 onclick="toggleSection('section_conv')">对话质量评测 ({len(results)} 个场景)</h2>
    <div id="section_conv" class="collapsible open">
        {"".join(cards)}
    </div>
</div>"""


DIM_LABELS = {
    "empathy": "共情质量",
    "professionalism": "专业性",
    "safety": "安全性",
    "guidance": "引导性",
    "accessibility": "去专业化",
}


def _dim_label(dim: str) -> str:
    return DIM_LABELS.get(dim, dim)


def _collect_review_items(
    module_results: list[ModuleResult],
    conversation_results: list[ConversationResult],
) -> list[dict]:
    items = []

    for r in module_results:
        if r.needs_human_review:
            items.append({
                "id": r.case_id,
                "type": "module",
                "module": r.module,
                "reason": r.details,
            })

    for cr in conversation_results:
        if cr.needs_human_review:
            low_dims = [f"{_dim_label(d)}({s}分)" for d, s in cr.scores.items() if s < 3]
            reasons = []
            if low_dims:
                reasons.append(f"低分维度: {', '.join(low_dims)}")
            if cr.red_flags_found:
                reasons.append(f"Red Flags: {', '.join(cr.red_flags_found)}")
            items.append({
                "id": cr.case_id,
                "type": "conversation",
                "module": "conversation",
                "reason": "; ".join(reasons) or "需要人工复核",
            })

    return items


def _render_review_section(items: list[dict]) -> str:
    rows = []
    for item in items:
        rows.append(f"""\
<div class="review-item">
    <b>{_esc(item['id'])}</b> [{_esc(item['module'])}] — {_esc(item['reason'])}
</div>""")

    return f"""\
<div class="section review-section">
    <h2>需人工复核项 ({len(items)} 项)</h2>
    {"".join(rows)}
</div>"""


def _render_footer() -> str:
    return """\
</div>
</body>
</html>"""
