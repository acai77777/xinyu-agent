"""
评测系统主入口
运行端到端模块评测和/或对话评测，生成 HTML 报告 + JSON 实际输出
"""
import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

# 让 server/ 目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.eval_modules import (
    run_module_evaluation,
    get_all_module_results,
    print_summary,
    PipelineResult,
    ModuleResult,
)
from evaluation.eval_conversation import run_conversation_evaluation
from evaluation.report import generate_report
from config import settings


def _save_results_json(
    pipeline_results: list[PipelineResult] | None,
    strategy_results: list[ModuleResult] | None,
    conversation_results: list | None,
    output_dir: str,
) -> str:
    """将评测实际输出保存为 JSON 文件，返回文件路径"""
    results_dir = Path(output_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_name = settings.main_model.replace("/", "_")
    filename = f"results_{model_name}_{timestamp}.json"
    filepath = results_dir / filename

    data = {
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "main_model": settings.main_model,
            "light_model": settings.light_model,
        },
        "pipeline": [],
        "strategy_standalone": [],
        "conversation": [],
    }

    if pipeline_results:
        for pr in pipeline_results:
            pipeline_item = {
                "case_id": pr.case_id,
                "input_text": pr.input_text,
                "source": pr.source,
                "overall_score": pr.overall_score,
                "all_passed": pr.all_passed,
                "modules": [],
            }
            for mr in pr.module_results:
                pipeline_item["modules"].append({
                    "module": mr.module,
                    "expected": mr.expected,
                    "actual": mr.actual,
                    "passed": mr.passed,
                    "score": mr.score,
                    "details": mr.details,
                    "needs_human_review": mr.needs_human_review,
                })
            data["pipeline"].append(pipeline_item)

    if strategy_results:
        for mr in strategy_results:
            data["strategy_standalone"].append({
                "case_id": mr.case_id,
                "input_text": mr.input_text,
                "expected": mr.expected,
                "actual": mr.actual,
                "passed": mr.passed,
                "score": mr.score,
                "details": mr.details,
            })

    if conversation_results:
        for cr in conversation_results:
            data["conversation"].append({
                "case_id": cr.case_id,
                "scenario": cr.scenario,
                "turn_count": cr.turn_count,
                "user_messages": cr.user_messages,
                "agent_responses": cr.agent_responses,
                "reference_responses": cr.reference_responses,
                "full_dialogue": cr.full_dialogue,
                "scores": cr.scores,
                "reasoning": cr.reasoning,
                "red_flags_found": cr.red_flags_found,
                "overall_comment": cr.overall_comment,
                "improvement_suggestions": cr.improvement_suggestions,
                "needs_human_review": cr.needs_human_review,
            })

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return str(filepath)


async def main():
    parser = argparse.ArgumentParser(description="心理学Agent评测系统")
    parser.add_argument(
        "--modules-only",
        action="store_true",
        help="只运行模块准确性评测（端到端流水线）",
    )
    parser.add_argument(
        "--conversation-only",
        action="store_true",
        help="只运行对话质量评测",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="eval_report.html",
        help="报告输出路径 (默认: eval_report.html)",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="测试用例数据目录 (默认: evaluation/data/)",
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default=None,
        help="实际输出保存目录 (默认: evaluation/results/)",
    )
    args = parser.parse_args()

    run_modules = not args.conversation_only
    run_conversations = not args.modules_only

    pipeline_results = None
    strategy_results = None
    conversation_results = None

    if run_modules:
        print("=" * 50)
        print("  端到端模块评测")
        print("=" * 50)
        pipeline_results, strategy_results = await run_module_evaluation(args.data_dir)
        print_summary(pipeline_results, strategy_results)

    if run_conversations:
        print("\n" + "=" * 50)
        print("  对话质量评测 (LLM-as-Judge)")
        print("=" * 50)
        conversation_results = await run_conversation_evaluation(args.data_dir)
        if conversation_results:
            all_scores = []
            for cr in conversation_results:
                all_scores.extend(cr.scores.values())
            avg = sum(all_scores) / len(all_scores) if all_scores else 0
            print(f"\n对话评测完成: {len(conversation_results)} 个场景, 平均 {avg:.1f}/5")

    # 保存实际输出 JSON
    results_dir = args.results_dir or str(Path(__file__).parent / "results")
    results_path = _save_results_json(
        pipeline_results, strategy_results, conversation_results, results_dir,
    )
    print(f"\n实际输出已保存: {results_path}")

    # 生成 HTML 报告
    print("\n" + "=" * 50)
    print("  生成报告")
    print("=" * 50)

    module_results = None
    if pipeline_results is not None:
        module_results = get_all_module_results(pipeline_results, strategy_results or [])

    report_path = generate_report(
        module_results=module_results,
        conversation_results=conversation_results,
        pipeline_results=pipeline_results,
        output_path=args.output,
    )
    print(f"报告已生成: {report_path}")

    # 汇总需要人工复核的项
    review_count = 0
    if module_results:
        review_count += sum(1 for r in module_results if r.needs_human_review)
    if conversation_results:
        review_count += sum(1 for r in conversation_results if r.needs_human_review)
    if review_count:
        print(f"\n共 {review_count} 项需要人工复核，请查看报告中的标注")


if __name__ == "__main__":
    asyncio.run(main())
