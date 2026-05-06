"""快速测试：只跑前3个case验证评测流程"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from evaluation.eval_modules import eval_pipeline_case, print_summary


async def main():
    data_path = Path(__file__).parent / "evaluation" / "data" / "module_cases.json"
    with open(data_path, "r", encoding="utf-8") as f:
        cases_data = json.load(f)

    cases = cases_data.get("cases", [])[:3]
    print(f"快速测试: 只跑前 {len(cases)} 个 case\n")

    results = []
    for case in cases:
        print(f"  运行 {case['id']}: {case['input'][:30]}...")
        r = await eval_pipeline_case(case)
        results.append(r)
        for mr in r.module_results:
            status = "PASS" if mr.passed else "FAIL"
            print(f"    [{status}] {mr.module}: {mr.details[:60]}")
        print()

    passed = sum(1 for r in results for mr in r.module_results if mr.passed)
    total = sum(len(r.module_results) for r in results)
    print(f"\n总计: {passed}/{total} 通过")


if __name__ == "__main__":
    asyncio.run(main())
